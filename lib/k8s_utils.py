"""
Kubernetes utility functions for CNI Migration Tool
"""

import os
import logging
from kubernetes import client, config

log = logging.getLogger("cni-migration.k8s_utils")

def get_kubernetes_client():
    """
    Initialize and return a Kubernetes API client.
    
    Returns:
        kubernetes.client.ApiClient: Initialized Kubernetes API client
    """
    try:
        # Try to load from kube config file
        config.load_kube_config()
        log.info("Loaded Kubernetes configuration from kube config file")
    except Exception as e:
        # If that fails, try to load in-cluster config
        try:
            config.load_incluster_config()
            log.info("Loaded in-cluster Kubernetes configuration")
        except Exception as in_cluster_e:
            log.error("Failed to load Kubernetes configuration: %s", str(e))
            log.error("In-cluster config also failed: %s", str(in_cluster_e))
            raise RuntimeError("Could not configure Kubernetes client") from e
    
    return client.ApiClient()

def get_node_info():
    """
    Get information about nodes in the cluster.
    
    Returns:
        list: List of node information dictionaries
    """
    api_client = get_kubernetes_client()
    core_v1 = client.CoreV1Api(api_client)
    
    nodes = []
    try:
        node_list = core_v1.list_node()
        for node in node_list.items:
            node_info = {
                'name': node.metadata.name,
                'labels': node.metadata.labels or {},
                'annotations': node.metadata.annotations or {},
                'taints': node.spec.taints or [],
                'conditions': {cond.type: cond.status for cond in node.status.conditions},
                'addresses': {addr.type: addr.address for addr in node.status.addresses},
                'capacity': {k: v for k, v in node.status.capacity.items()},
                'allocatable': {k: v for k, v in node.status.allocatable.items()},
            }
            nodes.append(node_info)
    except Exception as e:
        log.error("Error getting node information: %s", str(e))
        raise
    
    return nodes

def get_pod_cidr():
    """
    Get the Pod CIDR used in the cluster.
    
    Returns:
        str: Pod CIDR or None if not found
    """
    api_client = get_kubernetes_client()
    core_v1 = client.CoreV1Api(api_client)
    
    try:
        # Get the first node
        nodes = core_v1.list_node()
        if not nodes.items:
            log.warning("No nodes found in the cluster")
            return None
        
        # Check if the node has a podCIDR
        node = nodes.items[0]
        if hasattr(node.spec, 'pod_cidr') and node.spec.pod_cidr:
            return node.spec.pod_cidr
        
        # If not found in node spec, try to get it from cluster configuration
        # This is implementation-specific and might not work in all clusters
        log.warning("Pod CIDR not found in node spec, trying to get from ConfigMap")
        
        # Try to get from kube-system/kubeadm-config ConfigMap (for kubeadm clusters)
        try:
            kubeadm_config = core_v1.read_namespaced_config_map(
                name="kubeadm-config",
                namespace="kube-system"
            )
            if 'ClusterConfiguration' in kubeadm_config.data:
                import yaml
                cluster_config = yaml.safe_load(kubeadm_config.data['ClusterConfiguration'])
                if 'networking' in cluster_config and 'podSubnet' in cluster_config['networking']:
                    return cluster_config['networking']['podSubnet']
        except Exception as e:
            log.debug("Error getting kubeadm-config: %s", str(e))
        
        # Try to get from CNI configuration
        # This is highly dependent on the CNI implementation
        log.warning("Pod CIDR not found in kubeadm-config, CNI-specific methods would be needed")
        return None
    except Exception as e:
        log.error("Error getting Pod CIDR: %s", str(e))
        return None

def create_test_pods(namespace="cni-migration-test"):
    """
    Create test pods for connectivity validation.
    
    Args:
        namespace (str): Namespace to create test pods in
        
    Returns:
        list: Names of created pods
    """
    api_client = get_kubernetes_client()
    core_v1 = client.CoreV1Api(api_client)
    
    # Create namespace if it doesn't exist
    try:
        core_v1.read_namespace(name=namespace)
        log.info(f"Namespace {namespace} already exists")
    except client.rest.ApiException as e:
        if e.status == 404:
            log.info(f"Creating namespace {namespace}")
            ns_manifest = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
            core_v1.create_namespace(body=ns_manifest)
        else:
            raise
    
    # Define test pods
    test_pods = [
        {
            "name": "test-pod-1",
            "image": "nginx:latest",
            "labels": {"app": "test-pod-1"}
        },
        {
            "name": "test-pod-2",
            "image": "busybox:latest",
            "labels": {"app": "test-pod-2"},
            "command": ["sleep", "3600"]
        }
    ]
    
    created_pods = []
    for pod_def in test_pods:
        try:
            # Check if pod already exists
            try:
                core_v1.read_namespaced_pod(name=pod_def["name"], namespace=namespace)
                log.info(f"Pod {pod_def['name']} already exists in namespace {namespace}")
                created_pods.append(pod_def["name"])
                continue
            except client.rest.ApiException as e:
                if e.status != 404:
                    raise
            
            # Create pod
            pod_manifest = client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name=pod_def["name"],
                    namespace=namespace,
                    labels=pod_def["labels"]
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name=pod_def["name"],
                            image=pod_def["image"],
                            command=pod_def.get("command")
                        )
                    ]
                )
            )
            
            core_v1.create_namespaced_pod(namespace=namespace, body=pod_manifest)
            log.info(f"Created pod {pod_def['name']} in namespace {namespace}")
            created_pods.append(pod_def["name"])
        except Exception as e:
            log.error(f"Error creating pod {pod_def['name']}: {str(e)}")
    
    return created_pods

def delete_test_pods(namespace="cni-migration-test", delete_namespace=True):
    """
    Delete test pods and optionally the namespace.
    
    Args:
        namespace (str): Namespace containing test pods
        delete_namespace (bool): Whether to delete the namespace
        
    Returns:
        bool: True if successful, False otherwise
    """
    api_client = get_kubernetes_client()
    core_v1 = client.CoreV1Api(api_client)
    
    try:
        # Delete all pods in the namespace
        pod_list = core_v1.list_namespaced_pod(namespace=namespace)
        for pod in pod_list.items:
            try:
                core_v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace)
                log.info(f"Deleted pod {pod.metadata.name} in namespace {namespace}")
            except Exception as e:
                log.error(f"Error deleting pod {pod.metadata.name}: {str(e)}")
        
        # Delete the namespace if requested
        if delete_namespace:
            try:
                core_v1.delete_namespace(name=namespace)
                log.info(f"Deleted namespace {namespace}")
            except Exception as e:
                log.error(f"Error deleting namespace {namespace}: {str(e)}")
        
        return True
    except Exception as e:
        log.error(f"Error cleaning up test resources: {str(e)}")
        return False
