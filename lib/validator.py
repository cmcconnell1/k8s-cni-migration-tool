"""
Validator module for CNI Migration Tool

This module validates connectivity and policy enforcement before, during, and after migration.
"""

import os
import logging
import time
import yaml
import json
import subprocess
from kubernetes import client, config
from .k8s_utils import get_kubernetes_client, create_test_pods, delete_test_pods

log = logging.getLogger("cni-migration.validator")

def run_kubectl_command(command):
    """
    Run a kubectl command and return the output.

    Args:
        command (list): Command to run

    Returns:
        str: Command output
    """
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        log.error(f"Command failed: {' '.join(command)}")
        log.error(f"Error: {e.stderr}")
        raise

def check_pod_connectivity(source_pod, target_pod, namespace="cni-migration-test"):
    """
    Check connectivity between two pods.

    Args:
        source_pod (str): Source pod name
        target_pod (str): Target pod name
        namespace (str): Namespace containing the pods

    Returns:
        bool: True if connectivity is successful, False otherwise
    """
    try:
        # Get target pod IP
        api_client = get_kubernetes_client()
        core_v1 = client.CoreV1Api(api_client)
        pod = core_v1.read_namespaced_pod(name=target_pod, namespace=namespace)
        target_ip = pod.status.pod_ip

        if not target_ip:
            log.error(f"Target pod {target_pod} has no IP address")
            return False

        # Run curl from source pod to target pod
        command = [
            "kubectl", "exec", "-n", namespace, source_pod, "--",
            "curl", "--max-time", "5", "-s", target_ip
        ]

        output = run_kubectl_command(command)

        # Check if the output contains expected response
        return len(output) > 0
    except Exception as e:
        log.error(f"Error checking connectivity from {source_pod} to {target_pod}: {str(e)}")
        return False

def check_service_connectivity(source_pod, service_name, namespace="cni-migration-test"):
    """
    Check connectivity from a pod to a service.

    Args:
        source_pod (str): Source pod name
        service_name (str): Service name
        namespace (str): Namespace containing the pod and service

    Returns:
        bool: True if connectivity is successful, False otherwise
    """
    try:
        # Run curl from source pod to service
        command = [
            "kubectl", "exec", "-n", namespace, source_pod, "--",
            "curl", "--max-time", "5", "-s", f"{service_name}.{namespace}.svc.cluster.local"
        ]

        output = run_kubectl_command(command)

        # Check if the output contains expected response
        return len(output) > 0
    except Exception as e:
        log.error(f"Error checking connectivity from {source_pod} to service {service_name}: {str(e)}")
        return False

def check_external_connectivity(pod_name, external_url="www.google.com", namespace="cni-migration-test"):
    """
    Check connectivity from a pod to an external URL.

    Args:
        pod_name (str): Pod name
        external_url (str): External URL to check
        namespace (str): Namespace containing the pod

    Returns:
        bool: True if connectivity is successful, False otherwise
    """
    try:
        # Run curl from pod to external URL
        command = [
            "kubectl", "exec", "-n", namespace, pod_name, "--",
            "curl", "--max-time", "5", "-s", external_url
        ]

        output = run_kubectl_command(command)

        # Check if the output contains expected response
        return len(output) > 0
    except Exception as e:
        log.error(f"Error checking connectivity from {pod_name} to {external_url}: {str(e)}")
        return False

def check_dns_resolution(pod_name, hostname="kubernetes.default.svc.cluster.local", namespace="cni-migration-test"):
    """
    Check DNS resolution from a pod.

    Args:
        pod_name (str): Pod name
        hostname (str): Hostname to resolve
        namespace (str): Namespace containing the pod

    Returns:
        bool: True if DNS resolution is successful, False otherwise
    """
    try:
        # Run nslookup from pod
        command = [
            "kubectl", "exec", "-n", namespace, pod_name, "--",
            "nslookup", hostname
        ]

        output = run_kubectl_command(command)

        # Check if the output contains expected response
        return "Address" in output
    except Exception as e:
        log.error(f"Error checking DNS resolution from {pod_name} for {hostname}: {str(e)}")
        return False

def check_network_policy(namespace="cni-migration-test"):
    """
    Check if network policies are enforced.

    Args:
        namespace (str): Namespace to test in

    Returns:
        bool: True if network policies are enforced, False otherwise
    """
    try:
        api_client = get_kubernetes_client()
        core_v1 = client.CoreV1Api(api_client)
        networking_v1 = client.NetworkingV1Api(api_client)

        # Create test pods
        create_test_pods(namespace)

        # Wait for pods to be ready
        time.sleep(10)

        # Create a service for test-pod-1
        service_manifest = client.V1Service(
            metadata=client.V1ObjectMeta(
                name="test-service",
                namespace=namespace
            ),
            spec=client.V1ServiceSpec(
                selector={"app": "test-pod-1"},
                ports=[client.V1ServicePort(port=80, target_port=80)]
            )
        )

        try:
            core_v1.read_namespaced_service(name="test-service", namespace=namespace)
            log.info(f"Service test-service already exists in namespace {namespace}")
        except client.rest.ApiException as e:
            if e.status == 404:
                core_v1.create_namespaced_service(namespace=namespace, body=service_manifest)
                log.info(f"Created service test-service in namespace {namespace}")
            else:
                raise

        # Check connectivity before applying network policy
        pre_policy_connectivity = check_pod_connectivity("test-pod-2", "test-pod-1", namespace)

        # Create a network policy to deny traffic to test-pod-1
        policy_manifest = client.V1NetworkPolicy(
            metadata=client.V1ObjectMeta(
                name="deny-test-pod-1",
                namespace=namespace
            ),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(
                    match_labels={"app": "test-pod-1"}
                ),
                policy_types=["Ingress"],
                ingress=[]  # Empty ingress rules = deny all
            )
        )

        try:
            networking_v1.read_namespaced_network_policy(name="deny-test-pod-1", namespace=namespace)
            log.info(f"Network policy deny-test-pod-1 already exists in namespace {namespace}")
        except client.rest.ApiException as e:
            if e.status == 404:
                networking_v1.create_namespaced_network_policy(namespace=namespace, body=policy_manifest)
                log.info(f"Created network policy deny-test-pod-1 in namespace {namespace}")
            else:
                raise

        # Wait for policy to be applied
        time.sleep(10)

        # Check connectivity after applying network policy
        post_policy_connectivity = check_pod_connectivity("test-pod-2", "test-pod-1", namespace)

        # Clean up
        try:
            networking_v1.delete_namespaced_network_policy(name="deny-test-pod-1", namespace=namespace)
            log.info(f"Deleted network policy deny-test-pod-1 in namespace {namespace}")
        except Exception as e:
            log.warning(f"Error deleting network policy: {str(e)}")

        try:
            core_v1.delete_namespaced_service(name="test-service", namespace=namespace)
            log.info(f"Deleted service test-service in namespace {namespace}")
        except Exception as e:
            log.warning(f"Error deleting service: {str(e)}")

        # Network policy is enforced if connectivity was allowed before and denied after
        return pre_policy_connectivity and not post_policy_connectivity
    except Exception as e:
        log.error(f"Error checking network policy enforcement: {str(e)}")
        return False
    finally:
        # Clean up test pods
        delete_test_pods(namespace, delete_namespace=False)

def validate_connectivity(phase="pre", source_cni=None, target_cidr=None):
    """
    Validate connectivity and policy enforcement.

    Args:
        phase (str): Migration phase (pre, during, post)
        source_cni (str): Source CNI type (for during/post validation)
        target_cidr (str): Target CIDR for Cilium (for during/post validation)

    Returns:
        dict: Validation results
    """
    log.info(f"Validating connectivity ({phase} migration)")

    namespace = "cni-migration-test"

    # Create test pods
    pod_names = create_test_pods(namespace)

    # Wait for pods to be ready
    time.sleep(10)

    # Create a service for test-pod-1
    api_client = get_kubernetes_client()
    core_v1 = client.CoreV1Api(api_client)

    service_manifest = client.V1Service(
        metadata=client.V1ObjectMeta(
            name="test-service",
            namespace=namespace
        ),
        spec=client.V1ServiceSpec(
            selector={"app": "test-pod-1"},
            ports=[client.V1ServicePort(port=80, target_port=80)]
        )
    )

    try:
        core_v1.read_namespaced_service(name="test-service", namespace=namespace)
        log.info(f"Service test-service already exists in namespace {namespace}")
    except client.rest.ApiException as e:
        if e.status == 404:
            core_v1.create_namespaced_service(namespace=namespace, body=service_manifest)
            log.info(f"Created service test-service in namespace {namespace}")
        else:
            raise

    # Wait for service to be ready
    time.sleep(5)

    # Basic connectivity tests
    tests = [
        {
            "name": "Pod-to-Pod Connectivity",
            "function": check_pod_connectivity,
            "args": ["test-pod-2", "test-pod-1", namespace]
        },
        {
            "name": "Pod-to-Service Connectivity",
            "function": check_service_connectivity,
            "args": ["test-pod-2", "test-service", namespace]
        },
        {
            "name": "External Connectivity",
            "function": check_external_connectivity,
            "args": ["test-pod-2", "www.google.com", namespace]
        },
        {
            "name": "DNS Resolution",
            "function": check_dns_resolution,
            "args": ["test-pod-2", "kubernetes.default.svc.cluster.local", namespace]
        }
    ]

    # Add cross-CNI tests for during migration phase
    if phase == "during" and source_cni and target_cidr:
        # Create test pods on specific nodes
        # First, find a node with Cilium and a node without Cilium
        cilium_node = None
        non_cilium_node = None

        try:
            nodes = core_v1.list_node()
            for node in nodes.items:
                if node.metadata.labels and "io.cilium.migration/cilium-default" in node.metadata.labels:
                    cilium_node = node.metadata.name
                else:
                    non_cilium_node = node.metadata.name

                if cilium_node and non_cilium_node:
                    break

            if cilium_node and non_cilium_node:
                log.info(f"Found Cilium node: {cilium_node} and non-Cilium node: {non_cilium_node}")

                # Create a pod on the Cilium node
                cilium_pod_manifest = client.V1Pod(
                    metadata=client.V1ObjectMeta(
                        name="cilium-test-pod",
                        namespace=namespace,
                        labels={"app": "cilium-test-pod"}
                    ),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="cilium-test-pod",
                                image="nginx:latest"
                            )
                        ],
                        node_name=cilium_node
                    )
                )

                # Create a pod on the non-Cilium node
                non_cilium_pod_manifest = client.V1Pod(
                    metadata=client.V1ObjectMeta(
                        name="non-cilium-test-pod",
                        namespace=namespace,
                        labels={"app": "non-cilium-test-pod"}
                    ),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="non-cilium-test-pod",
                                image="nginx:latest"
                            )
                        ],
                        node_name=non_cilium_node
                    )
                )

                try:
                    core_v1.create_namespaced_pod(namespace=namespace, body=cilium_pod_manifest)
                    core_v1.create_namespaced_pod(namespace=namespace, body=non_cilium_pod_manifest)

                    # Wait for pods to be ready
                    for _ in range(30):
                        cilium_pod = core_v1.read_namespaced_pod(name="cilium-test-pod", namespace=namespace)
                        non_cilium_pod = core_v1.read_namespaced_pod(name="non-cilium-test-pod", namespace=namespace)

                        if (cilium_pod.status.phase == "Running" and
                            non_cilium_pod.status.phase == "Running"):
                            break
                        time.sleep(1)

                    # Create services for the pods
                    cilium_svc_manifest = client.V1Service(
                        metadata=client.V1ObjectMeta(
                            name="cilium-test-service",
                            namespace=namespace
                        ),
                        spec=client.V1ServiceSpec(
                            selector={"app": "cilium-test-pod"},
                            ports=[client.V1ServicePort(port=80, target_port=80)]
                        )
                    )

                    non_cilium_svc_manifest = client.V1Service(
                        metadata=client.V1ObjectMeta(
                            name="non-cilium-test-service",
                            namespace=namespace
                        ),
                        spec=client.V1ServiceSpec(
                            selector={"app": "non-cilium-test-pod"},
                            ports=[client.V1ServicePort(port=80, target_port=80)]
                        )
                    )

                    core_v1.create_namespaced_service(namespace=namespace, body=cilium_svc_manifest)
                    core_v1.create_namespaced_service(namespace=namespace, body=non_cilium_svc_manifest)

                    # Wait for services to be ready
                    time.sleep(5)

                    # Get pod IPs
                    cilium_pod = core_v1.read_namespaced_pod(name="cilium-test-pod", namespace=namespace)
                    non_cilium_pod = core_v1.read_namespaced_pod(name="non-cilium-test-pod", namespace=namespace)

                    cilium_pod_ip = cilium_pod.status.pod_ip
                    non_cilium_pod_ip = non_cilium_pod.status.pod_ip

                    # Verify pod IPs are from the expected CIDRs
                    is_cilium_ip = False
                    if target_cidr and cilium_pod_ip:
                        import ipaddress
                        try:
                            target_network = ipaddress.ip_network(target_cidr)
                            cilium_ip = ipaddress.ip_address(cilium_pod_ip)
                            is_cilium_ip = cilium_ip in target_network
                        except Exception as e:
                            log.warning(f"Error checking if IP is in CIDR: {str(e)}")

                    log.info(f"Cilium pod IP: {cilium_pod_ip} (from Cilium CIDR: {is_cilium_ip})")
                    log.info(f"Non-Cilium pod IP: {non_cilium_pod_ip}")

                    # Add cross-CNI connectivity tests
                    tests.extend([
                        {
                            "name": "Cilium Pod to Non-Cilium Pod Connectivity",
                            "function": check_pod_connectivity,
                            "args": ["cilium-test-pod", "non-cilium-test-pod", namespace]
                        },
                        {
                            "name": "Non-Cilium Pod to Cilium Pod Connectivity",
                            "function": check_pod_connectivity,
                            "args": ["non-cilium-test-pod", "cilium-test-pod", namespace]
                        },
                        {
                            "name": "Cilium Pod to Non-Cilium Service Connectivity",
                            "function": check_service_connectivity,
                            "args": ["cilium-test-pod", "non-cilium-test-service", namespace]
                        },
                        {
                            "name": "Non-Cilium Pod to Cilium Service Connectivity",
                            "function": check_service_connectivity,
                            "args": ["non-cilium-test-pod", "cilium-test-service", namespace]
                        }
                    ])

                except Exception as e:
                    log.error(f"Error setting up cross-CNI tests: {str(e)}")
        except Exception as e:
            log.error(f"Error finding Cilium and non-Cilium nodes: {str(e)}")

    # Add network policy test for post-migration phase
    if phase == "post":
        tests.append({
            "name": "Network Policy Enforcement",
            "function": check_network_policy,
            "args": [namespace]
        })

    # Run tests
    results = []
    passed_tests = 0
    total_tests = len(tests)

    for test in tests:
        try:
            log.info(f"Running test: {test['name']}")
            success = test["function"](*test["args"])
            results.append({
                "name": test["name"],
                "success": success,
                "message": "Test passed" if success else "Test failed"
            })

            if success:
                passed_tests += 1
        except Exception as e:
            log.error(f"Error running test {test['name']}: {str(e)}")
            results.append({
                "name": test["name"],
                "success": False,
                "message": f"Error: {str(e)}"
            })

    # Clean up
    try:
        # Delete services
        core_v1.delete_namespaced_service(name="test-service", namespace=namespace)
        log.info(f"Deleted service test-service in namespace {namespace}")

        if phase == "during":
            try:
                core_v1.delete_namespaced_service(name="cilium-test-service", namespace=namespace)
                core_v1.delete_namespaced_service(name="non-cilium-test-service", namespace=namespace)
                log.info("Deleted cross-CNI test services")
            except Exception as e:
                log.warning(f"Error deleting cross-CNI test services: {str(e)}")

            try:
                core_v1.delete_namespaced_pod(name="cilium-test-pod", namespace=namespace)
                core_v1.delete_namespaced_pod(name="non-cilium-test-pod", namespace=namespace)
                log.info("Deleted cross-CNI test pods")
            except Exception as e:
                log.warning(f"Error deleting cross-CNI test pods: {str(e)}")
    except Exception as e:
        log.warning(f"Error during cleanup: {str(e)}")

    delete_test_pods(namespace, delete_namespace=True)

    # Prepare results
    issues = [f"{result['name']}: {result['message']}" for result in results if not result['success']]

    # Create a detailed report
    report = {
        "phase": phase,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "success": passed_tests == total_tests,
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "results": results,
        "issues": issues
    }

    # Save report to file
    report_dir = "validation-reports"
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, f"connectivity-report-{phase}-{time.strftime('%Y%m%d-%H%M%S')}.json")

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    log.info(f"Validation report saved to {report_file}")

    return report
