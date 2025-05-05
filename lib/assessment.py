"""
Assessment module for CNI Migration Tool

This module analyzes the current CNI configuration and determines migration difficulty.
It detects the current CNI type, counts network policies, and assesses how difficult
the migration to Cilium will be based on the current environment.
"""

# Standard library imports
import os  # File and directory operations
import logging  # Logging functionality
import yaml  # YAML parsing and generation
import json  # JSON parsing and generation
import time  # Time-related functions

# Third-party imports
from kubernetes import client, config  # Kubernetes API client
from kubernetes.stream import stream  # For streaming exec commands to pods

# Local imports
from .k8s_utils import get_kubernetes_client, get_pod_cidr  # Utility functions for Kubernetes

# Set up module logger
log = logging.getLogger("cni-migration.assessment")

def detect_cni_type():
    """
    Detect the current CNI type in the cluster by examining various Kubernetes resources.

    This function looks for indicators of different CNI plugins by checking:
    1. DaemonSets and their containers
    2. Deployments and their containers
    3. ConfigMaps with CNI configuration
    4. Custom Resource Definitions (CRDs) specific to CNIs
    5. CNI configuration files on nodes

    Returns:
        dict: Information about the detected CNI including:
            - cni_type: The detected CNI type (calico, flannel, weave, etc.)
            - version: The detected CNI version if available
            - config: The CNI configuration if found
            - details: Additional details about the CNI components
    """
    log.info("Detecting CNI type...")

    # Initialize Kubernetes client APIs for accessing different resource types
    api_client = get_kubernetes_client()
    apps_v1 = client.AppsV1Api(api_client)  # For DaemonSets and Deployments
    core_v1 = client.CoreV1Api(api_client)  # For Pods, ConfigMaps, etc.

    # Define indicators for each CNI type to help with detection
    # Each CNI has specific components, namespaces, configmaps, and CRDs
    cni_indicators = {
        'calico': {
            'components': ['calico-node', 'calico-kube-controllers', 'calico-typha'],  # Component names
            'namespaces': ['kube-system', 'calico-system'],  # Namespaces where components run
            'configmaps': ['calico-config', 'cni-config'],  # ConfigMaps with CNI configuration
            'crds': ['felixconfigurations.crd.projectcalico.org', 'bgpconfigurations.crd.projectcalico.org']  # CRDs
        },
        'flannel': {
            'components': ['kube-flannel-ds', 'flannel'],
            'namespaces': ['kube-system', 'kube-flannel'],
            'configmaps': ['kube-flannel-cfg'],
            'crds': []  # Flannel doesn't use CRDs
        },
        'weave': {
            'components': ['weave-net'],
            'namespaces': ['kube-system'],
            'configmaps': ['weave-net'],
            'crds': []  # Weave doesn't use CRDs
        },
        'cilium': {
            'components': ['cilium', 'cilium-operator'],
            'namespaces': ['kube-system', 'cilium'],
            'configmaps': ['cilium-config'],
            'crds': ['ciliumnodes.cilium.io', 'ciliumnetworkpolicies.cilium.io']
        },
        'aws-cni': {
            'components': ['aws-node', 'aws-vpc-cni'],
            'namespaces': ['kube-system'],
            'configmaps': ['amazon-vpc-cni'],
            'crds': ['eniconfigs.crd.k8s.amazonaws.com']
        },
        'azure-cni': {
            'components': ['azure-cni', 'azure-vnet'],
            'namespaces': ['kube-system'],
            'configmaps': ['azure-cni-config'],
            'crds': []
        },
        'antrea': {
            'components': ['antrea-agent', 'antrea-controller'],
            'namespaces': ['kube-system', 'antrea-system'],
            'configmaps': ['antrea-config'],
            'crds': ['antreaagentinfos.crd.antrea.io', 'antreacontrollerinfos.crd.antrea.io']
        }
    }

    # Initialize variables to store detection results
    detected_cni = None  # Will hold the detected CNI type
    cni_version = None   # Will hold the detected CNI version
    cni_details = {}     # Will hold detailed information about the CNI

    # First detection method: Check DaemonSets
    # DaemonSets are commonly used to deploy CNI components on all nodes
    try:
        # Get all DaemonSets across all namespaces
        daemonsets = apps_v1.list_daemon_set_for_all_namespaces()

        # Iterate through each DaemonSet looking for CNI indicators
        for ds in daemonsets.items:
            ds_name = ds.metadata.name
            ds_namespace = ds.metadata.namespace

            # Check if this DaemonSet matches any known CNI indicators
            for cni, indicators in cni_indicators.items():
                # Check if the DaemonSet name contains a CNI component name and is in the expected namespace
                if any(indicator in ds_name for indicator in indicators['components']) and ds_namespace in indicators['namespaces']:
                    # We found a match! Record the CNI type
                    detected_cni = cni

                    # Store details about the DaemonSet
                    cni_details['daemonset'] = {
                        'name': ds_name,
                        'namespace': ds_namespace,
                        'desired': ds.status.desired_number_scheduled,  # How many nodes should run this
                        'current': ds.status.current_number_scheduled,  # How many nodes are running this
                        'ready': ds.status.number_ready  # How many instances are ready
                    }

                    # Try to extract the CNI version from the container image
                    if ds.spec.template.spec.containers:
                        container = ds.spec.template.spec.containers[0]  # Get the first container
                        image = container.image  # Get the container image
                        cni_details['image'] = image  # Store the image name

                        # Extract version from image tag if available
                        if ':' in image:
                            cni_version = image.split(':')[-1]  # Get the part after the colon

                        # Extract and store resource requirements
                        if container.resources:
                            cni_details['resources'] = {
                                'limits': container.resources.limits,  # CPU/memory limits
                                'requests': container.resources.requests  # CPU/memory requests
                            }

                    log.info(f"Detected CNI {detected_cni} (version: {cni_version}) from DaemonSet {ds_namespace}/{ds_name}")
                    break  # Stop checking other CNI types once we've found a match

            # If we've found a CNI, stop checking other DaemonSets
            if detected_cni:
                break
    except Exception as e:
        # Log any errors but continue with other detection methods
        log.warning(f"Error checking daemonsets: {str(e)}")

    # Second detection method: Check Deployments
    # If we didn't find a CNI in DaemonSets, check Deployments
    # Some CNI components (especially controllers) are deployed as Deployments
    if not detected_cni:
        try:
            # Get all Deployments across all namespaces
            deployments = apps_v1.list_deployment_for_all_namespaces()

            # Iterate through each Deployment looking for CNI indicators
            for deploy in deployments.items:
                deploy_name = deploy.metadata.name
                deploy_namespace = deploy.metadata.namespace

                # Check if this Deployment matches any known CNI indicators
                for cni, indicators in cni_indicators.items():
                    # Check if the Deployment name contains a CNI component name and is in the expected namespace
                    if any(indicator in deploy_name for indicator in indicators['components']) and deploy_namespace in indicators['namespaces']:
                        # We found a match! Record the CNI type
                        detected_cni = cni

                        # Store details about the Deployment
                        cni_details['deployment'] = {
                            'name': deploy_name,
                            'namespace': deploy_namespace,
                            'replicas': deploy.spec.replicas,  # Desired number of replicas
                            'available': deploy.status.available_replicas if deploy.status.available_replicas else 0  # Available replicas
                        }

                        # Try to extract the CNI version from the container image
                        if deploy.spec.template.spec.containers:
                            container = deploy.spec.template.spec.containers[0]  # Get the first container
                            image = container.image  # Get the container image
                            cni_details['image'] = image  # Store the image name

                            # Extract version from image tag if available
                            if ':' in image:
                                cni_version = image.split(':')[-1]  # Get the part after the colon

                            # Extract and store resource requirements
                            if container.resources:
                                cni_details['resources'] = {
                                    'limits': container.resources.limits,  # CPU/memory limits
                                    'requests': container.resources.requests  # CPU/memory requests
                                }

                        log.info(f"Detected CNI {detected_cni} (version: {cni_version}) from Deployment {deploy_namespace}/{deploy_name}")
                        break  # Stop checking other CNI types once we've found a match

                # If we've found a CNI, stop checking other Deployments
                if detected_cni:
                    break
        except Exception as e:
            # Log any errors but continue with other detection methods
            log.warning(f"Error checking deployments: {str(e)}")

    # Third detection method: Check ConfigMaps for CNI configuration
    # If we've detected a CNI, look for its configuration in ConfigMaps
    # ConfigMaps often contain the CNI configuration and settings
    cni_config = None  # Will hold the CNI configuration if found
    if detected_cni:
        try:
            # Get all ConfigMaps across all namespaces
            configmaps = core_v1.list_config_map_for_all_namespaces()

            # Iterate through each ConfigMap looking for CNI configuration
            for cm in configmaps.items:
                cm_name = cm.metadata.name
                cm_namespace = cm.metadata.namespace

                # Check if this ConfigMap matches the expected name and namespace for the detected CNI
                if cm_name in cni_indicators[detected_cni]['configmaps'] and cm_namespace in cni_indicators[detected_cni]['namespaces']:
                    log.info(f"Found CNI ConfigMap: {cm_namespace}/{cm_name}")

                    # Store the ConfigMap data as the CNI configuration
                    cni_config = cm.data

                    # Store details about the ConfigMap
                    cni_details['configmap'] = {
                        'name': cm_name,
                        'namespace': cm_namespace,
                        'data_keys': list(cm.data.keys()) if cm.data else []  # List of configuration keys
                    }
                    break  # Stop once we've found a matching ConfigMap
        except Exception as e:
            # Log any errors but continue with other detection methods
            log.warning(f"Error checking configmaps: {str(e)}")

    # Fourth detection method: Check for Custom Resource Definitions (CRDs) related to the CNI
    # Many CNIs (especially newer ones) use CRDs to define their resources
    if detected_cni:
        try:
            # Get the API extensions client for accessing CRDs
            api_ext = client.ApiextensionsV1Api(api_client)

            # Get all CRDs in the cluster
            crds = api_ext.list_custom_resource_definition()

            # List to store CNI-related CRDs
            cni_crds = []

            # Iterate through each CRD looking for CNI-related ones
            for crd in crds.items:
                crd_name = crd.metadata.name

                # Check if this CRD matches any of the patterns for the detected CNI
                if any(crd_pattern in crd_name for crd_pattern in cni_indicators[detected_cni]['crds']):
                    cni_crds.append(crd_name)  # Add to the list of CNI-related CRDs
                    log.info(f"Found CNI-related CRD: {crd_name}")

            # If we found any CNI-related CRDs, store them in the details
            if cni_crds:
                cni_details['crds'] = cni_crds
        except Exception as e:
            # Log any errors but continue with other detection methods
            log.warning(f"Error checking CRDs: {str(e)}")

    # Fifth detection method: Check for CNI configuration files directly on the nodes
    # This is the most direct way to detect the CNI, as the configuration files
    # are stored on each node in the /etc/cni/net.d/ directory
    try:
        # Get all nodes in the cluster
        nodes = core_v1.list_node()
        if nodes.items:
            # Just check the first node (CNI config should be the same on all nodes)
            node = nodes.items[0]
            node_name = node.metadata.name
            log.info(f"Checking CNI configuration on node: {node_name}")

            # Create a temporary pod to check CNI configuration
            # We need to create a pod because we can't directly access the node's filesystem
            pod_name = "cni-config-checker"
            pod_manifest = client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name=pod_name,
                    namespace="kube-system"  # Use kube-system namespace for system operations
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="checker",
                            image="busybox:latest",  # Use a small utility image
                            command=["sleep", "300"],  # Keep the pod running for 5 minutes
                            volume_mounts=[
                                client.V1VolumeMount(
                                    name="cni-config",
                                    mount_path="/host/etc/cni/net.d"  # Mount the CNI config directory
                                )
                            ]
                        )
                    ],
                    volumes=[
                        client.V1Volume(
                            name="cni-config",
                            host_path=client.V1HostPathVolumeSource(
                                path="/etc/cni/net.d"  # Path to CNI config on the host
                            )
                        )
                    ],
                    node_name=node_name,  # Schedule on the specific node
                    restart_policy="Never",  # Don't restart if it fails
                    tolerations=[
                        client.V1Toleration(
                            operator="Exists"  # Tolerate any taints on the node
                        )
                    ]
                )
            )

            try:
                # Try to create the pod on the node
                core_v1.create_namespaced_pod(namespace="kube-system", body=pod_manifest)
                log.info(f"Created CNI config checker pod on node {node_name}")

                # Wait for pod to be ready (up to 10 seconds)
                for _ in range(10):
                    pod = core_v1.read_namespaced_pod(name=pod_name, namespace="kube-system")
                    if pod.status.phase == "Running":
                        log.info("CNI config checker pod is running")
                        break
                    time.sleep(1)  # Wait 1 second before checking again

                if pod.status.phase == "Running":
                    # Check CNI config files by listing the directory
                    exec_command = ["/bin/sh", "-c", "ls -la /host/etc/cni/net.d/"]
                    resp = stream(
                        core_v1.connect_get_namespaced_pod_exec,
                        pod_name,
                        "kube-system",
                        command=exec_command,
                        stderr=True, stdin=False, stdout=True, tty=False
                    )

                    # Store the list of files in the CNI config directory
                    cni_details['cni_config_files'] = resp.strip().split('\n')
                    log.info(f"Found CNI config files: {len(cni_details['cni_config_files'])} entries")

                    # Try to get content of the first .conf or .conflist file
                    # These files contain the actual CNI configuration
                    exec_command = ["/bin/sh", "-c", "grep -l . /host/etc/cni/net.d/*.conf* | head -1 | xargs cat"]
                    try:
                        resp = stream(
                            core_v1.connect_get_namespaced_pod_exec,
                            pod_name,
                            "kube-system",
                            command=exec_command,
                            stderr=True, stdin=False, stdout=True, tty=False
                        )
                        # Store the content of the CNI configuration file
                        cni_details['cni_config_content'] = resp.strip()
                        log.info("Successfully read CNI configuration content")
                    except Exception as e:
                        log.warning(f"Error reading CNI config content: {str(e)}")
            except Exception as e:
                log.warning(f"Error creating or using checker pod: {str(e)}")
            finally:
                # Clean up the pod when we're done
                try:
                    core_v1.delete_namespaced_pod(name=pod_name, namespace="kube-system")
                    log.info("Deleted CNI config checker pod")
                except Exception as e:
                    log.warning(f"Error deleting checker pod: {str(e)}")
    except Exception as e:
        # Log any errors but continue with other detection methods
        log.warning(f"Error checking nodes: {str(e)}")

    # Sixth detection method: Check Pod CIDR configuration
    # The Pod CIDR range can provide additional information about the CNI
    try:
        # Get the Pod CIDR from the cluster configuration
        pod_cidr = get_pod_cidr()
        if pod_cidr:
            # Store the Pod CIDR in the details
            cni_details['pod_cidr'] = pod_cidr
            log.info(f"Detected Pod CIDR: {pod_cidr}")
    except Exception as e:
        # Log any errors but continue
        log.warning(f"Error getting Pod CIDR: {str(e)}")

    # If we couldn't detect a CNI after all methods, mark it as unknown
    if not detected_cni:
        log.warning("Could not detect CNI type")
        detected_cni = "unknown"  # Default to unknown if we can't detect

    # Return all the information we've gathered about the CNI
    return {
        'cni_type': detected_cni,  # The detected CNI type (calico, flannel, etc.)
        'version': cni_version,    # The detected CNI version
        'config': cni_config,      # The CNI configuration
        'details': cni_details     # Additional details about the CNI
    }

def count_network_policies(output_dir=None):
    """
    Count and optionally save network policies in the cluster.

    This function finds all network policies in the cluster, including:
    1. Standard Kubernetes NetworkPolicies
    2. Calico-specific network policies
    3. Cilium-specific network policies

    If an output directory is provided, it will save all policies to files
    for later analysis and conversion.

    Args:
        output_dir (str, optional): Directory to save network policies to.
                                   If None, policies are counted but not saved.

    Returns:
        dict: Information about network policies, including:
            - k8s_policies: Number of standard Kubernetes NetworkPolicies
            - calico_policies: Number of Calico-specific NetworkPolicies
            - cilium_policies: Number of Cilium-specific NetworkPolicies
            - total: Total number of network policies
    """
    log.info("Counting network policies...")

    # Initialize Kubernetes client for accessing network policies
    api_client = get_kubernetes_client()
    networking_v1 = client.NetworkingV1Api(api_client)  # For standard K8s NetworkPolicies

    # First policy type: Standard Kubernetes NetworkPolicies
    # These are part of the core Kubernetes API
    k8s_policies = []
    try:
        # Get all NetworkPolicies across all namespaces
        policies = networking_v1.list_network_policy_for_all_namespaces()
        k8s_policies = policies.items  # Store the list of policies
        log.info(f"Found {len(k8s_policies)} Kubernetes NetworkPolicies")
    except Exception as e:
        log.warning(f"Error getting Kubernetes NetworkPolicies: {str(e)}")

    # Second policy type: Calico network policies
    # These are custom resources defined by Calico
    calico_policies = []
    try:
        # Use the CustomObjects API to access Calico-specific resources
        api_instance = client.CustomObjectsApi(api_client)
        calico_policies_list = api_instance.list_cluster_custom_object(
            group="projectcalico.org",  # API group for Calico resources
            version="v3",               # API version
            plural="networkpolicies"    # Resource type
        )
        calico_policies = calico_policies_list.get('items', [])  # Get the list of policies
        log.info(f"Found {len(calico_policies)} Calico NetworkPolicies")
    except Exception as e:
        # This error is expected if Calico is not installed
        log.debug(f"Error getting Calico NetworkPolicies (this is normal if Calico is not installed): {str(e)}")

    # Third policy type: Cilium network policies
    # These are custom resources defined by Cilium
    cilium_policies = []
    try:
        # Use the CustomObjects API to access Cilium-specific resources
        api_instance = client.CustomObjectsApi(api_client)
        cilium_policies_list = api_instance.list_cluster_custom_object(
            group="cilium.io",           # API group for Cilium resources
            version="v2",                # API version
            plural="ciliumnetworkpolicies"  # Resource type
        )
        cilium_policies = cilium_policies_list.get('items', [])  # Get the list of policies
        log.info(f"Found {len(cilium_policies)} Cilium NetworkPolicies")
    except Exception as e:
        # This error is expected if Cilium is not installed
        log.debug(f"Error getting Cilium NetworkPolicies (this is normal if Cilium is not installed): {str(e)}")

    # If an output directory is provided, save all policies to files
    # This is useful for later analysis and conversion
    if output_dir:
        # Create subdirectories for each policy type
        os.makedirs(os.path.join(output_dir, 'k8s'), exist_ok=True)      # For standard K8s policies
        os.makedirs(os.path.join(output_dir, 'calico'), exist_ok=True)   # For Calico policies
        os.makedirs(os.path.join(output_dir, 'cilium'), exist_ok=True)   # For Cilium policies

        # Save standard Kubernetes NetworkPolicies
        for policy in k8s_policies:
            # Create a unique filename based on namespace and policy name
            policy_name = f"{policy.metadata.namespace}.{policy.metadata.name}"
            file_path = os.path.join(output_dir, 'k8s', f"{policy_name}.yaml")

            # Write the policy to a YAML file
            with open(file_path, 'w') as f:
                # Convert the policy object to a serializable format before dumping to YAML
                yaml.dump(client.ApiClient().sanitize_for_serialization(policy), f)

        # Save Calico NetworkPolicies
        for policy in calico_policies:
            # Create a unique filename based on namespace and policy name
            policy_name = f"{policy['metadata']['namespace']}.{policy['metadata']['name']}"
            file_path = os.path.join(output_dir, 'calico', f"{policy_name}.yaml")

            # Write the policy to a YAML file
            with open(file_path, 'w') as f:
                yaml.dump(policy, f)

        # Save Cilium NetworkPolicies
        for policy in cilium_policies:
            # Create a unique filename based on namespace and policy name
            policy_name = f"{policy['metadata']['namespace']}.{policy['metadata']['name']}"
            file_path = os.path.join(output_dir, 'cilium', f"{policy_name}.yaml")

            # Write the policy to a YAML file
            with open(file_path, 'w') as f:
                yaml.dump(policy, f)

    # Return a summary of the policies found
    return {
        'k8s_policies': len(k8s_policies),       # Number of standard K8s policies
        'calico_policies': len(calico_policies), # Number of Calico policies
        'cilium_policies': len(cilium_policies), # Number of Cilium policies
        'total': len(k8s_policies) + len(calico_policies) + len(cilium_policies)  # Total count
    }

def assess_migration_difficulty(cni_info, policy_info):
    """
    Assess the difficulty of migrating to Cilium based on current configuration.

    This function analyzes the current CNI type and network policies to determine
    how difficult the migration to Cilium will be. It considers factors such as:
    - The current CNI type (some CNIs are easier to migrate from than others)
    - The number of network policies (more policies = more complex migration)
    - The presence of CNI-specific policies (requires conversion)

    The difficulty is categorized as:
    - "Easy": Simple migration with minimal risk
    - "Moderate": Requires careful planning but is generally straightforward
    - "Complex": Requires extensive planning and testing
    - "Not needed": Already using Cilium

    Args:
        cni_info (dict): Information about the current CNI from detect_cni_type()
        policy_info (dict): Information about network policies from count_network_policies()

    Returns:
        tuple: (difficulty, reasons)
            - difficulty (str): Migration difficulty assessment (Easy, Moderate, Complex, Not needed)
            - reasons (list): List of reasons for the difficulty assessment
    """
    # Start with the assumption that migration is Easy
    difficulty = "Easy"
    reasons = []  # List to store reasons for the difficulty assessment

    # Special case 1: If already using Cilium, migration is not needed
    if cni_info['cni_type'] == 'cilium':
        return "Not needed (already using Cilium)", ["Already using Cilium"]

    # Special case 2: If CNI type is unknown, migration is complex
    if cni_info['cni_type'] == 'unknown':
        return "Complex", ["Unknown CNI type"]

    # Factor 1: Assess based on CNI type
    # Different CNIs have different migration complexity
    if cni_info['cni_type'] == 'calico':
        difficulty = "Moderate"
        reasons.append("Calico uses a similar policy model to Cilium, but migration requires careful planning")
    elif cni_info['cni_type'] == 'flannel':
        difficulty = "Easy"
        reasons.append("Flannel is a simple CNI with limited features, making migration straightforward")
    elif cni_info['cni_type'] == 'weave':
        difficulty = "Moderate"
        reasons.append("Weave has some unique features that need careful consideration during migration")

    # Factor 2: Assess based on network policy count
    # More policies = more complex migration
    if policy_info['total'] == 0:
        reasons.append("No network policies to migrate")
    elif policy_info['total'] < 10:
        reasons.append(f"Small number of network policies ({policy_info['total']})")
    elif policy_info['total'] < 50:
        # Upgrade difficulty to Moderate if it was Easy
        if difficulty == "Easy":
            difficulty = "Moderate"
        reasons.append(f"Moderate number of network policies ({policy_info['total']})")
    else:
        # Large number of policies makes migration complex regardless of CNI
        difficulty = "Complex"
        reasons.append(f"Large number of network policies ({policy_info['total']})")

    # Factor 3: Assess based on custom resource policies
    # CNI-specific policies require conversion
    if policy_info['calico_policies'] > 0:
        # Upgrade difficulty to at least Moderate
        if difficulty != "Complex":
            difficulty = "Moderate"
        reasons.append(f"Has {policy_info['calico_policies']} Calico-specific network policies that need conversion")

    return difficulty, reasons

def assess_current_cni(output_dir):
    """
    Assess the current CNI configuration and determine migration difficulty.

    This is the main entry point for the assessment module. It:
    1. Detects the current CNI type
    2. Counts and saves network policies
    3. Assesses migration difficulty
    4. Saves the assessment results as JSON and a human-readable report

    The assessment provides a comprehensive overview of the current CNI setup
    and how difficult it will be to migrate to Cilium.

    Args:
        output_dir (str): Directory to store assessment results.
                         If None, results are not saved to disk.

    Returns:
        dict: Assessment results containing:
            - cni_type: The detected CNI type
            - cni_version: The detected CNI version
            - policy_count: Total number of network policies
            - k8s_policies: Number of standard Kubernetes NetworkPolicies
            - calico_policies: Number of Calico-specific NetworkPolicies
            - cilium_policies: Number of Cilium-specific NetworkPolicies
            - difficulty: Migration difficulty assessment (Easy, Moderate, Complex)
            - reasons: List of reasons for the difficulty assessment
    """
    # Step 1: Create output directories if needed
    if output_dir:
        # Create the main output directory
        os.makedirs(output_dir, exist_ok=True)

        # Create a subdirectory for network policies
        policies_dir = os.path.join(output_dir, 'policies')
        os.makedirs(policies_dir, exist_ok=True)
        log.info(f"Created output directories: {output_dir}")

    # Step 2: Detect the current CNI type
    log.info("Starting CNI detection...")
    cni_info = detect_cni_type()
    log.info(f"Detected CNI: {cni_info['cni_type']} (version: {cni_info['version']})")

    # Step 3: Count and save network policies
    log.info("Counting network policies...")
    # If output_dir is provided, save policies to the 'policies' subdirectory
    policy_info = count_network_policies(os.path.join(output_dir, 'policies') if output_dir else None)
    log.info(f"Found {policy_info['total']} network policies")

    # Step 4: Assess migration difficulty based on CNI type and policies
    log.info("Assessing migration difficulty...")
    difficulty, reasons = assess_migration_difficulty(cni_info, policy_info)
    log.info(f"Migration difficulty: {difficulty}")
    for reason in reasons:
        log.info(f"- {reason}")

    # Step 5: Prepare the assessment results
    results = {
        'cni_type': cni_info['cni_type'],       # The detected CNI type
        'cni_version': cni_info['version'],     # The detected CNI version
        'policy_count': policy_info['total'],   # Total number of network policies
        'k8s_policies': policy_info['k8s_policies'],       # Standard K8s policies
        'calico_policies': policy_info['calico_policies'], # Calico-specific policies
        'cilium_policies': policy_info['cilium_policies'], # Cilium-specific policies
        'difficulty': difficulty,  # Migration difficulty assessment
        'reasons': reasons         # Reasons for the difficulty assessment
    }

    # Step 6: Save the assessment results if output_dir is provided
    if output_dir:
        # Save as JSON for machine readability
        assessment_file = os.path.join(output_dir, 'assessment.json')
        with open(assessment_file, 'w') as f:
            json.dump(results, f, indent=2)  # Pretty-print the JSON
        log.info(f"Saved assessment results to {assessment_file}")

        # Create a human-readable Markdown report
        report_file = os.path.join(output_dir, 'assessment_report.md')
        with open(report_file, 'w') as f:
            # Write the report header
            f.write("# CNI Migration Assessment Report\n\n")

            # Write CNI information
            f.write(f"## Current CNI: {cni_info['cni_type']}\n")
            if cni_info['version']:
                f.write(f"Version: {cni_info['version']}\n")

            # Write network policy information
            f.write("\n## Network Policies\n\n")
            f.write(f"- Kubernetes NetworkPolicies: {policy_info['k8s_policies']}\n")
            f.write(f"- Calico NetworkPolicies: {policy_info['calico_policies']}\n")
            f.write(f"- Cilium NetworkPolicies: {policy_info['cilium_policies']}\n")
            f.write(f"- Total: {policy_info['total']}\n\n")

            # Write migration difficulty assessment
            f.write(f"## Migration Difficulty: {difficulty}\n\n")
            f.write("Reasons:\n")
            for reason in reasons:
                f.write(f"- {reason}\n")
        log.info(f"Created human-readable report at {report_file}")

    return results
