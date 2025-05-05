"""
Policy Converter module for CNI Migration Tool

This module converts network policies from various CNI formats to Cilium format.
"""

import os
import logging
import yaml
import json
import time
from kubernetes import client, config
from .k8s_utils import get_kubernetes_client

log = logging.getLogger("cni-migration.policy_converter")

def convert_k8s_to_cilium(k8s_policy):
    """
    Convert a Kubernetes NetworkPolicy to Cilium NetworkPolicy.

    Args:
        k8s_policy (dict): Kubernetes NetworkPolicy

    Returns:
        dict: Cilium NetworkPolicy
    """
    log.info(f"Converting Kubernetes NetworkPolicy {k8s_policy['metadata']['name']} to Cilium format")

    # Create a basic Cilium NetworkPolicy structure
    cilium_policy = {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": {
            "name": k8s_policy["metadata"]["name"],
            "namespace": k8s_policy["metadata"]["namespace"]
        },
        "spec": {
            "endpointSelector": {}
        }
    }

    # Copy labels from the original policy
    if "labels" in k8s_policy["metadata"]:
        cilium_policy["metadata"]["labels"] = k8s_policy["metadata"]["labels"]

    # Convert podSelector to endpointSelector
    if "podSelector" in k8s_policy["spec"]:
        cilium_policy["spec"]["endpointSelector"] = {
            "matchLabels": k8s_policy["spec"]["podSelector"].get("matchLabels", {}),
            "matchExpressions": k8s_policy["spec"]["podSelector"].get("matchExpressions", [])
        }
        # Remove empty fields
        if not cilium_policy["spec"]["endpointSelector"]["matchLabels"]:
            del cilium_policy["spec"]["endpointSelector"]["matchLabels"]
        if not cilium_policy["spec"]["endpointSelector"]["matchExpressions"]:
            del cilium_policy["spec"]["endpointSelector"]["matchExpressions"]

    # Convert ingress rules
    if "ingress" in k8s_policy["spec"]:
        cilium_policy["spec"]["ingress"] = []
        for ingress_rule in k8s_policy["spec"]["ingress"]:
            cilium_ingress = {}

            # Convert from selector
            if "from" in ingress_rule:
                from_endpoints = []
                for from_item in ingress_rule["from"]:
                    if "podSelector" in from_item:
                        from_endpoints.append({
                            "matchLabels": from_item["podSelector"].get("matchLabels", {}),
                            "matchExpressions": from_item["podSelector"].get("matchExpressions", [])
                        })
                    elif "namespaceSelector" in from_item:
                        from_endpoints.append({
                            "matchLabels": from_item["namespaceSelector"].get("matchLabels", {}),
                            "matchExpressions": from_item["namespaceSelector"].get("matchExpressions", [])
                        })
                    elif "ipBlock" in from_item:
                        # Convert ipBlock to CIDR rule
                        cidr = from_item["ipBlock"]["cidr"]
                        cilium_ingress["fromCIDR"] = [cidr]

                        # Handle except CIDRs
                        if "except" in from_item["ipBlock"]:
                            cilium_ingress["fromCIDRSet"] = [
                                {"cidr": cidr, "except": from_item["ipBlock"]["except"]}
                            ]

                if from_endpoints:
                    cilium_ingress["fromEndpoints"] = from_endpoints

            # Convert ports
            if "ports" in ingress_rule:
                to_ports = []
                for port in ingress_rule["ports"]:
                    port_rule = {
                        "ports": [{
                            "port": str(port.get("port", "")),
                            "protocol": port.get("protocol", "TCP")
                        }]
                    }
                    to_ports.append(port_rule)

                if to_ports:
                    cilium_ingress["toPorts"] = to_ports

            cilium_policy["spec"]["ingress"].append(cilium_ingress)

    # Convert egress rules
    if "egress" in k8s_policy["spec"]:
        cilium_policy["spec"]["egress"] = []
        for egress_rule in k8s_policy["spec"]["egress"]:
            cilium_egress = {}

            # Convert to selector
            if "to" in egress_rule:
                to_endpoints = []
                for to_item in egress_rule["to"]:
                    if "podSelector" in to_item:
                        to_endpoints.append({
                            "matchLabels": to_item["podSelector"].get("matchLabels", {}),
                            "matchExpressions": to_item["podSelector"].get("matchExpressions", [])
                        })
                    elif "namespaceSelector" in to_item:
                        to_endpoints.append({
                            "matchLabels": to_item["namespaceSelector"].get("matchLabels", {}),
                            "matchExpressions": to_item["namespaceSelector"].get("matchExpressions", [])
                        })
                    elif "ipBlock" in to_item:
                        # Convert ipBlock to CIDR rule
                        cidr = to_item["ipBlock"]["cidr"]
                        cilium_egress["toCIDR"] = [cidr]

                        # Handle except CIDRs
                        if "except" in to_item["ipBlock"]:
                            cilium_egress["toCIDRSet"] = [
                                {"cidr": cidr, "except": to_item["ipBlock"]["except"]}
                            ]

                if to_endpoints:
                    cilium_egress["toEndpoints"] = to_endpoints

            # Convert ports
            if "ports" in egress_rule:
                to_ports = []
                for port in egress_rule["ports"]:
                    port_rule = {
                        "ports": [{
                            "port": str(port.get("port", "")),
                            "protocol": port.get("protocol", "TCP")
                        }]
                    }
                    to_ports.append(port_rule)

                if to_ports:
                    cilium_egress["toPorts"] = to_ports

            cilium_policy["spec"]["egress"].append(cilium_egress)

    # Set policy types
    if "policyTypes" in k8s_policy["spec"]:
        cilium_policy["spec"]["policyTypes"] = k8s_policy["spec"]["policyTypes"]

    return cilium_policy

def convert_calico_to_cilium(calico_policy):
    """
    Convert a Calico NetworkPolicy to Cilium NetworkPolicy.

    Args:
        calico_policy (dict): Calico NetworkPolicy

    Returns:
        dict: Cilium NetworkPolicy
    """
    log.info(f"Converting Calico NetworkPolicy {calico_policy['metadata']['name']} to Cilium format")

    # Create a basic Cilium NetworkPolicy structure
    cilium_policy = {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": {
            "name": calico_policy["metadata"]["name"],
            "namespace": calico_policy["metadata"].get("namespace", "default")
        },
        "spec": {
            "endpointSelector": {}
        }
    }

    # Copy labels from the original policy
    if "labels" in calico_policy["metadata"]:
        cilium_policy["metadata"]["labels"] = calico_policy["metadata"]["labels"]

    # Convert selector to endpointSelector
    if "selector" in calico_policy["spec"]:
        # Calico uses a different selector format, need to parse it
        selector = calico_policy["spec"]["selector"]
        # This is a simplified conversion - in reality, you'd need to parse the Calico selector syntax
        cilium_policy["spec"]["endpointSelector"] = {
            "matchLabels": {"calico-selector": selector}
        }
        # Add a comment about the original selector
        cilium_policy["metadata"]["annotations"] = cilium_policy["metadata"].get("annotations", {})
        cilium_policy["metadata"]["annotations"]["original-calico-selector"] = selector

    # Convert ingress rules
    if "ingress" in calico_policy["spec"]:
        cilium_policy["spec"]["ingress"] = []
        for ingress_rule in calico_policy["spec"]["ingress"]:
            cilium_ingress = {}

            # Convert source
            if "source" in ingress_rule:
                source = ingress_rule["source"]

                # Handle selector
                if "selector" in source:
                    cilium_ingress["fromEndpoints"] = [{
                        "matchLabels": {"calico-selector": source["selector"]}
                    }]

                # Handle namespaceSelector
                if "namespaceSelector" in source:
                    cilium_ingress["fromEndpoints"] = cilium_ingress.get("fromEndpoints", [])
                    cilium_ingress["fromEndpoints"].append({
                        "matchLabels": {"calico-namespace-selector": source["namespaceSelector"]}
                    })

                # Handle nets (CIDRs)
                if "nets" in source:
                    cilium_ingress["fromCIDR"] = source["nets"]

            # Convert destination ports
            if "destination" in ingress_rule and "ports" in ingress_rule["destination"]:
                to_ports = []
                for port in ingress_rule["destination"]["ports"]:
                    # Parse port range if needed
                    if ":" in port:
                        start, end = port.split(":")
                        port_rule = {
                            "ports": [{
                                "port": start,
                                "endPort": end,
                                "protocol": ingress_rule["protocol"] if "protocol" in ingress_rule else "TCP"
                            }]
                        }
                    else:
                        port_rule = {
                            "ports": [{
                                "port": port,
                                "protocol": ingress_rule["protocol"] if "protocol" in ingress_rule else "TCP"
                            }]
                        }
                    to_ports.append(port_rule)

                if to_ports:
                    cilium_ingress["toPorts"] = to_ports

            cilium_policy["spec"]["ingress"].append(cilium_ingress)

    # Convert egress rules
    if "egress" in calico_policy["spec"]:
        cilium_policy["spec"]["egress"] = []
        for egress_rule in calico_policy["spec"]["egress"]:
            cilium_egress = {}

            # Convert destination
            if "destination" in egress_rule:
                destination = egress_rule["destination"]

                # Handle selector
                if "selector" in destination:
                    cilium_egress["toEndpoints"] = [{
                        "matchLabels": {"calico-selector": destination["selector"]}
                    }]

                # Handle namespaceSelector
                if "namespaceSelector" in destination:
                    cilium_egress["toEndpoints"] = cilium_egress.get("toEndpoints", [])
                    cilium_egress["toEndpoints"].append({
                        "matchLabels": {"calico-namespace-selector": destination["namespaceSelector"]}
                    })

                # Handle nets (CIDRs)
                if "nets" in destination:
                    cilium_egress["toCIDR"] = destination["nets"]

                # Convert destination ports
                if "ports" in destination:
                    to_ports = []
                    for port in destination["ports"]:
                        # Parse port range if needed
                        if ":" in port:
                            start, end = port.split(":")
                            port_rule = {
                                "ports": [{
                                    "port": start,
                                    "endPort": end,
                                    "protocol": egress_rule["protocol"] if "protocol" in egress_rule else "TCP"
                                }]
                            }
                        else:
                            port_rule = {
                                "ports": [{
                                    "port": port,
                                    "protocol": egress_rule["protocol"] if "protocol" in egress_rule else "TCP"
                                }]
                            }
                        to_ports.append(port_rule)

                    if to_ports:
                        cilium_egress["toPorts"] = to_ports

            cilium_policy["spec"]["egress"].append(cilium_egress)

    # Add a warning comment about manual verification
    cilium_policy["metadata"]["annotations"] = cilium_policy["metadata"].get("annotations", {})
    cilium_policy["metadata"]["annotations"]["conversion-warning"] = "This policy was automatically converted from Calico format. Please verify its correctness."

    return cilium_policy

def validate_cilium_policy(policy):
    """
    Validate a Cilium NetworkPolicy.

    Args:
        policy (dict): Cilium NetworkPolicy

    Returns:
        tuple: (is_valid, validation_errors)
    """
    validation_errors = []

    # Check required fields
    if 'apiVersion' not in policy:
        validation_errors.append("Missing apiVersion")
    elif policy['apiVersion'] != 'cilium.io/v2':
        validation_errors.append(f"Invalid apiVersion: {policy['apiVersion']}, expected: cilium.io/v2")

    if 'kind' not in policy:
        validation_errors.append("Missing kind")
    elif policy['kind'] != 'CiliumNetworkPolicy':
        validation_errors.append(f"Invalid kind: {policy['kind']}, expected: CiliumNetworkPolicy")

    if 'metadata' not in policy:
        validation_errors.append("Missing metadata")
    else:
        if 'name' not in policy['metadata']:
            validation_errors.append("Missing metadata.name")

    if 'spec' not in policy:
        validation_errors.append("Missing spec")
    else:
        if 'endpointSelector' not in policy['spec']:
            validation_errors.append("Missing spec.endpointSelector")

    # Check for common errors in ingress/egress rules
    if 'spec' in policy:
        if 'ingress' in policy['spec']:
            for i, rule in enumerate(policy['spec']['ingress']):
                # Check for empty fromEndpoints
                if 'fromEndpoints' in rule and not rule['fromEndpoints']:
                    validation_errors.append(f"Empty fromEndpoints in ingress rule {i}")

                # Check for invalid port definitions
                if 'toPorts' in rule:
                    for j, port_rule in enumerate(rule['toPorts']):
                        if 'ports' not in port_rule or not port_rule['ports']:
                            validation_errors.append(f"Missing or empty ports in ingress rule {i}, toPorts {j}")

        if 'egress' in policy['spec']:
            for i, rule in enumerate(policy['spec']['egress']):
                # Check for empty toEndpoints
                if 'toEndpoints' in rule and not rule['toEndpoints']:
                    validation_errors.append(f"Empty toEndpoints in egress rule {i}")

                # Check for invalid port definitions
                if 'toPorts' in rule:
                    for j, port_rule in enumerate(rule['toPorts']):
                        if 'ports' not in port_rule or not port_rule['ports']:
                            validation_errors.append(f"Missing or empty ports in egress rule {i}, toPorts {j}")

    return len(validation_errors) == 0, validation_errors

def convert_policies(source_cni, input_dir, output_dir, validate=True, apply=False):
    """
    Convert network policies from source CNI to Cilium format.

    Args:
        source_cni (str): Source CNI type (calico, flannel, weave)
        input_dir (str): Directory containing network policies
        output_dir (str): Directory to store converted policies
        validate (bool): Whether to validate converted policies
        apply (bool): Whether to apply converted policies to the cluster

    Returns:
        dict: Conversion results
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create subdirectories for different policy types
    os.makedirs(os.path.join(output_dir, 'k8s'), exist_ok=True)
    if source_cni == 'calico':
        os.makedirs(os.path.join(output_dir, 'calico'), exist_ok=True)

    # Create a directory for validation errors
    validation_dir = os.path.join(output_dir, 'validation')
    os.makedirs(validation_dir, exist_ok=True)

    converted_count = 0
    failed_count = 0
    validation_failed_count = 0
    applied_count = 0

    # Track all policies for summary
    all_policies = []

    # Process Kubernetes NetworkPolicies
    k8s_dir = os.path.join(input_dir, 'k8s')
    if os.path.exists(k8s_dir):
        for filename in os.listdir(k8s_dir):
            if not filename.endswith('.yaml') and not filename.endswith('.yml'):
                continue

            policy_info = {
                'source_type': 'k8s',
                'filename': filename,
                'status': 'failed',
                'validation': None,
                'applied': False,
                'errors': []
            }

            try:
                with open(os.path.join(k8s_dir, filename), 'r') as f:
                    k8s_policy = yaml.safe_load(f)

                cilium_policy = convert_k8s_to_cilium(k8s_policy)

                # Validate the converted policy
                if validate:
                    is_valid, validation_errors = validate_cilium_policy(cilium_policy)
                    policy_info['validation'] = is_valid

                    if not is_valid:
                        policy_info['errors'].extend(validation_errors)
                        validation_failed_count += 1

                        # Save validation errors
                        with open(os.path.join(validation_dir, f"k8s-{filename}.errors"), 'w') as f:
                            for error in validation_errors:
                                f.write(f"{error}\n")

                        log.warning(f"Validation failed for converted Kubernetes NetworkPolicy {filename}")

                # Save the converted policy
                output_filename = os.path.join(output_dir, 'k8s', filename)
                with open(output_filename, 'w') as f:
                    yaml.dump(cilium_policy, f)

                policy_info['status'] = 'converted'
                log.info(f"Converted Kubernetes NetworkPolicy {filename} to Cilium format")
                converted_count += 1

                # Apply the policy if requested and valid
                if apply and (not validate or (validate and policy_info['validation'])):
                    try:
                        api_client = get_kubernetes_client()
                        custom_api = client.CustomObjectsApi(api_client)

                        # Apply the policy
                        custom_api.create_namespaced_custom_object(
                            group="cilium.io",
                            version="v2",
                            namespace=cilium_policy['metadata']['namespace'],
                            plural="ciliumnetworkpolicies",
                            body=cilium_policy
                        )

                        policy_info['applied'] = True
                        applied_count += 1
                        log.info(f"Applied converted policy {filename} to the cluster")
                    except Exception as e:
                        policy_info['errors'].append(f"Error applying policy: {str(e)}")
                        log.error(f"Error applying converted policy {filename}: {str(e)}")
            except Exception as e:
                policy_info['errors'].append(f"Error converting policy: {str(e)}")
                log.error(f"Error converting Kubernetes NetworkPolicy {filename}: {str(e)}")
                failed_count += 1

            all_policies.append(policy_info)

    # Process Calico NetworkPolicies if source_cni is calico
    if source_cni == 'calico':
        calico_dir = os.path.join(input_dir, 'calico')
        if os.path.exists(calico_dir):
            for filename in os.listdir(calico_dir):
                if not filename.endswith('.yaml') and not filename.endswith('.yml'):
                    continue

                policy_info = {
                    'source_type': 'calico',
                    'filename': filename,
                    'status': 'failed',
                    'validation': None,
                    'applied': False,
                    'errors': []
                }

                try:
                    with open(os.path.join(calico_dir, filename), 'r') as f:
                        calico_policy = yaml.safe_load(f)

                    cilium_policy = convert_calico_to_cilium(calico_policy)

                    # Validate the converted policy
                    if validate:
                        is_valid, validation_errors = validate_cilium_policy(cilium_policy)
                        policy_info['validation'] = is_valid

                        if not is_valid:
                            policy_info['errors'].extend(validation_errors)
                            validation_failed_count += 1

                            # Save validation errors
                            with open(os.path.join(validation_dir, f"calico-{filename}.errors"), 'w') as f:
                                for error in validation_errors:
                                    f.write(f"{error}\n")

                            log.warning(f"Validation failed for converted Calico NetworkPolicy {filename}")

                    # Save the converted policy
                    output_filename = os.path.join(output_dir, 'calico', filename)
                    with open(output_filename, 'w') as f:
                        yaml.dump(cilium_policy, f)

                    policy_info['status'] = 'converted'
                    log.info(f"Converted Calico NetworkPolicy {filename} to Cilium format")
                    converted_count += 1

                    # Apply the policy if requested and valid
                    if apply and (not validate or (validate and policy_info['validation'])):
                        try:
                            api_client = get_kubernetes_client()
                            custom_api = client.CustomObjectsApi(api_client)

                            # Apply the policy
                            custom_api.create_namespaced_custom_object(
                                group="cilium.io",
                                version="v2",
                                namespace=cilium_policy['metadata']['namespace'],
                                plural="ciliumnetworkpolicies",
                                body=cilium_policy
                            )

                            policy_info['applied'] = True
                            applied_count += 1
                            log.info(f"Applied converted policy {filename} to the cluster")
                        except Exception as e:
                            policy_info['errors'].append(f"Error applying policy: {str(e)}")
                            log.error(f"Error applying converted policy {filename}: {str(e)}")
                except Exception as e:
                    policy_info['errors'].append(f"Error converting policy: {str(e)}")
                    log.error(f"Error converting Calico NetworkPolicy {filename}: {str(e)}")
                    failed_count += 1

                all_policies.append(policy_info)

    # Create a detailed summary file
    summary = {
        'source_cni': source_cni,
        'converted_count': converted_count,
        'failed_count': failed_count,
        'validation_failed_count': validation_failed_count,
        'applied_count': applied_count,
        'total_count': converted_count + failed_count,
        'policies': all_policies,
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(os.path.join(output_dir, 'conversion_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2)

    # Create a human-readable report
    with open(os.path.join(output_dir, 'conversion_report.md'), 'w') as f:
        f.write(f"# Network Policy Conversion Report\n\n")
        f.write(f"**Source CNI:** {source_cni}\n")
        f.write(f"**Timestamp:** {summary['timestamp']}\n\n")

        f.write(f"## Summary\n\n")
        f.write(f"- Total policies: {summary['total_count']}\n")
        f.write(f"- Successfully converted: {summary['converted_count']}\n")
        f.write(f"- Failed to convert: {summary['failed_count']}\n")

        if validate:
            f.write(f"- Failed validation: {summary['validation_failed_count']}\n")

        if apply:
            f.write(f"- Applied to cluster: {summary['applied_count']}\n")

        f.write(f"\n## Policy Details\n\n")

        # Group policies by status
        policies_by_status = {
            'converted': [],
            'failed': []
        }

        for policy in all_policies:
            policies_by_status[policy['status']].append(policy)

        # List converted policies
        f.write(f"### Successfully Converted Policies\n\n")
        if policies_by_status['converted']:
            f.write(f"| Source | Filename | Validation | Applied |\n")
            f.write(f"|--------|----------|------------|--------|\n")

            for policy in policies_by_status['converted']:
                validation_status = "N/A"
                if policy['validation'] is not None:
                    validation_status = "✅ Passed" if policy['validation'] else "❌ Failed"

                applied_status = "✅ Yes" if policy['applied'] else "❌ No"

                f.write(f"| {policy['source_type']} | {policy['filename']} | {validation_status} | {applied_status} |\n")
        else:
            f.write(f"No policies were successfully converted.\n")

        # List failed policies
        f.write(f"\n### Failed Policies\n\n")
        if policies_by_status['failed']:
            f.write(f"| Source | Filename | Errors |\n")
            f.write(f"|--------|----------|--------|\n")

            for policy in policies_by_status['failed']:
                errors = "<br>".join(policy['errors'])
                f.write(f"| {policy['source_type']} | {policy['filename']} | {errors} |\n")
        else:
            f.write(f"No policies failed conversion.\n")

    return summary
