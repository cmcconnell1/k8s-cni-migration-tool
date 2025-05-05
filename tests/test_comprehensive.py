#!/usr/bin/env python3
"""
Comprehensive test script for the CNI Migration Tool.

This script tests the core functionality of the tool without requiring a real Kubernetes cluster.
It uses mock data and simulated environments to test each component.
"""

import os
import sys
import json
import yaml
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import modules to test
from lib.assessment import detect_cni_type, assess_migration_difficulty, assess_current_cni
from lib.policy_converter import convert_k8s_to_cilium, convert_calico_to_cilium, validate_cilium_policy
from lib.migration_planner import generate_migration_plan
from lib.validator import check_pod_connectivity, validate_connectivity

class TestCNIMigrationTool(unittest.TestCase):
    """Test cases for CNI Migration Tool."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test outputs
        self.test_dir = tempfile.mkdtemp()
        self.assessment_dir = os.path.join(self.test_dir, 'assessment')
        self.policies_dir = os.path.join(self.assessment_dir, 'policies')
        self.k8s_policies_dir = os.path.join(self.policies_dir, 'k8s')
        self.calico_policies_dir = os.path.join(self.policies_dir, 'calico')
        self.converted_dir = os.path.join(self.test_dir, 'converted')
        
        # Create directories
        os.makedirs(self.assessment_dir, exist_ok=True)
        os.makedirs(self.k8s_policies_dir, exist_ok=True)
        os.makedirs(self.calico_policies_dir, exist_ok=True)
        os.makedirs(self.converted_dir, exist_ok=True)
        
        # Create sample Kubernetes NetworkPolicy
        self.k8s_policy = {
            'apiVersion': 'networking.k8s.io/v1',
            'kind': 'NetworkPolicy',
            'metadata': {
                'name': 'test-network-policy',
                'namespace': 'default'
            },
            'spec': {
                'podSelector': {
                    'matchLabels': {
                        'app': 'test'
                    }
                },
                'policyTypes': ['Ingress', 'Egress'],
                'ingress': [
                    {
                        'from': [
                            {
                                'podSelector': {
                                    'matchLabels': {
                                        'app': 'frontend'
                                    }
                                }
                            }
                        ],
                        'ports': [
                            {
                                'protocol': 'TCP',
                                'port': 80
                            }
                        ]
                    }
                ],
                'egress': [
                    {
                        'to': [
                            {
                                'podSelector': {
                                    'matchLabels': {
                                        'app': 'database'
                                    }
                                }
                            }
                        ],
                        'ports': [
                            {
                                'protocol': 'TCP',
                                'port': 5432
                            }
                        ]
                    }
                ]
            }
        }
        
        # Create sample Calico NetworkPolicy
        self.calico_policy = {
            'apiVersion': 'projectcalico.org/v3',
            'kind': 'NetworkPolicy',
            'metadata': {
                'name': 'test-calico-policy',
                'namespace': 'default'
            },
            'spec': {
                'selector': 'app == "test"',
                'ingress': [
                    {
                        'source': {
                            'selector': 'app == "frontend"'
                        },
                        'destination': {
                            'ports': ['80']
                        }
                    }
                ],
                'egress': [
                    {
                        'destination': {
                            'selector': 'app == "database"',
                            'ports': ['5432']
                        }
                    }
                ],
                'types': ['Ingress', 'Egress']
            }
        }
        
        # Write sample policies to files
        with open(os.path.join(self.k8s_policies_dir, 'test-policy.yaml'), 'w') as f:
            yaml.dump(self.k8s_policy, f)
        
        with open(os.path.join(self.calico_policies_dir, 'test-calico-policy.yaml'), 'w') as f:
            yaml.dump(self.calico_policy, f)
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    @patch('lib.assessment.get_kubernetes_client')
    @patch('lib.assessment.client.AppsV1Api')
    @patch('lib.assessment.client.CoreV1Api')
    def test_detect_cni_type(self, mock_core_v1, mock_apps_v1, mock_get_client):
        """Test CNI type detection."""
        # Mock Kubernetes client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock DaemonSet for Calico
        mock_ds = MagicMock()
        mock_ds.metadata.name = 'calico-node'
        mock_ds.metadata.namespace = 'kube-system'
        mock_ds.spec.template.spec.containers = [MagicMock()]
        mock_ds.spec.template.spec.containers[0].image = 'calico/node:v3.24.1'
        
        # Mock DaemonSet list
        mock_ds_list = MagicMock()
        mock_ds_list.items = [mock_ds]
        mock_apps_v1.return_value.list_daemon_set_for_all_namespaces.return_value = mock_ds_list
        
        # Mock empty ConfigMap list
        mock_cm_list = MagicMock()
        mock_cm_list.items = []
        mock_core_v1.return_value.list_config_map_for_all_namespaces.return_value = mock_cm_list
        
        # Mock empty Node list
        mock_node_list = MagicMock()
        mock_node_list.items = []
        mock_core_v1.return_value.list_node.return_value = mock_node_list
        
        # Call function
        result = detect_cni_type()
        
        # Check result
        self.assertEqual(result['cni_type'], 'calico')
        self.assertEqual(result['version'], 'v3.24.1')
    
    def test_convert_k8s_to_cilium(self):
        """Test conversion of Kubernetes NetworkPolicy to Cilium NetworkPolicy."""
        # Convert policy
        cilium_policy = convert_k8s_to_cilium(self.k8s_policy)
        
        # Check result
        self.assertEqual(cilium_policy['apiVersion'], 'cilium.io/v2')
        self.assertEqual(cilium_policy['kind'], 'CiliumNetworkPolicy')
        self.assertEqual(cilium_policy['metadata']['name'], 'test-network-policy')
        self.assertEqual(cilium_policy['metadata']['namespace'], 'default')
        self.assertEqual(cilium_policy['spec']['endpointSelector']['matchLabels']['app'], 'test')
        
        # Check ingress rules
        self.assertTrue('ingress' in cilium_policy['spec'])
        self.assertTrue('fromEndpoints' in cilium_policy['spec']['ingress'][0])
        self.assertEqual(cilium_policy['spec']['ingress'][0]['fromEndpoints'][0]['matchLabels']['app'], 'frontend')
        
        # Check egress rules
        self.assertTrue('egress' in cilium_policy['spec'])
        self.assertTrue('toEndpoints' in cilium_policy['spec']['egress'][0])
        self.assertEqual(cilium_policy['spec']['egress'][0]['toEndpoints'][0]['matchLabels']['app'], 'database')
    
    def test_convert_calico_to_cilium(self):
        """Test conversion of Calico NetworkPolicy to Cilium NetworkPolicy."""
        # Convert policy
        cilium_policy = convert_calico_to_cilium(self.calico_policy)
        
        # Check result
        self.assertEqual(cilium_policy['apiVersion'], 'cilium.io/v2')
        self.assertEqual(cilium_policy['kind'], 'CiliumNetworkPolicy')
        self.assertEqual(cilium_policy['metadata']['name'], 'test-calico-policy')
        self.assertEqual(cilium_policy['metadata']['namespace'], 'default')
        
        # Check annotations
        self.assertTrue('annotations' in cilium_policy['metadata'])
        self.assertTrue('original-calico-selector' in cilium_policy['metadata']['annotations'])
        self.assertEqual(cilium_policy['metadata']['annotations']['original-calico-selector'], 'app == "test"')
        
        # Check ingress rules
        self.assertTrue('ingress' in cilium_policy['spec'])
        self.assertTrue('fromEndpoints' in cilium_policy['spec']['ingress'][0])
        
        # Check egress rules
        self.assertTrue('egress' in cilium_policy['spec'])
        self.assertTrue('toEndpoints' in cilium_policy['spec']['egress'][0])
    
    def test_validate_cilium_policy(self):
        """Test validation of Cilium NetworkPolicy."""
        # Create valid Cilium policy
        valid_policy = {
            'apiVersion': 'cilium.io/v2',
            'kind': 'CiliumNetworkPolicy',
            'metadata': {
                'name': 'test-policy',
                'namespace': 'default'
            },
            'spec': {
                'endpointSelector': {
                    'matchLabels': {
                        'app': 'test'
                    }
                },
                'ingress': [
                    {
                        'fromEndpoints': [
                            {
                                'matchLabels': {
                                    'app': 'frontend'
                                }
                            }
                        ],
                        'toPorts': [
                            {
                                'ports': [
                                    {
                                        'port': '80',
                                        'protocol': 'TCP'
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        
        # Create invalid Cilium policy (missing required fields)
        invalid_policy = {
            'apiVersion': 'cilium.io/v2',
            'kind': 'CiliumNetworkPolicy',
            'metadata': {
                'name': 'test-policy',
                'namespace': 'default'
            },
            'spec': {
                # Missing endpointSelector
                'ingress': [
                    {
                        # Empty fromEndpoints
                        'fromEndpoints': [],
                        'toPorts': [
                            {
                                # Missing ports
                            }
                        ]
                    }
                ]
            }
        }
        
        # Validate policies
        valid_result, valid_errors = validate_cilium_policy(valid_policy)
        invalid_result, invalid_errors = validate_cilium_policy(invalid_policy)
        
        # Check results
        self.assertTrue(valid_result)
        self.assertEqual(len(valid_errors), 0)
        
        self.assertFalse(invalid_result)
        self.assertTrue(len(invalid_errors) > 0)
        self.assertTrue(any('endpointSelector' in error for error in invalid_errors))
    
    @patch('lib.migration_planner.detect_cni_type')
    @patch('lib.migration_planner.get_pod_cidr')
    @patch('lib.migration_planner.count_network_policies')
    @patch('lib.migration_planner.get_kubernetes_client')
    @patch('lib.migration_planner.client.CoreV1Api')
    def test_generate_migration_plan(self, mock_core_v1, mock_get_client, mock_count_policies, 
                                     mock_get_pod_cidr, mock_detect_cni):
        """Test migration plan generation."""
        # Mock CNI detection
        mock_detect_cni.return_value = {
            'cni_type': 'calico',
            'version': 'v3.24.1',
            'details': {
                'pod_cidr': '10.244.0.0/16'
            }
        }
        
        # Mock Pod CIDR
        mock_get_pod_cidr.return_value = '10.244.0.0/16'
        
        # Mock policy count
        mock_count_policies.return_value = {
            'k8s_policies': 5,
            'calico_policies': 3,
            'cilium_policies': 0,
            'total': 8
        }
        
        # Mock node list
        mock_node = MagicMock()
        mock_node_list = MagicMock()
        mock_node_list.items = [mock_node, mock_node, mock_node]  # 3 nodes
        mock_core_v1.return_value.list_node.return_value = mock_node_list
        
        # Generate plan
        output_file = os.path.join(self.test_dir, 'migration-plan.md')
        result = generate_migration_plan('10.245.0.0/16', 'hybrid', output_file)
        
        # Check result
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_file))
        
        # Check plan content
        with open(output_file, 'r') as f:
            plan_content = f.read()
        
        # Check for key sections
        self.assertIn('Cilium Migration Plan - Hybrid Per-Node Approach', plan_content)
        self.assertIn('Current CNI: calico', plan_content)
        self.assertIn('Current Pod CIDR: 10.244.0.0/16', plan_content)
        self.assertIn('Target CIDR for Cilium: 10.245.0.0/16', plan_content)
        self.assertIn('Number of nodes: 3', plan_content)
        self.assertIn('Number of network policies: 8', plan_content)
        
        # Check for migration steps
        self.assertIn('Prepare the Environment', plan_content)
        self.assertIn('Prepare Cilium Deployment', plan_content)
        self.assertIn('Deploy Cilium as a Secondary Overlay', plan_content)
        self.assertIn('Migrate Nodes One by One', plan_content)
        self.assertIn('Complete the Migration', plan_content)
        self.assertIn('Post-Migration Verification', plan_content)
        self.assertIn('Rollback Plan', plan_content)

if __name__ == '__main__':
    unittest.main()
