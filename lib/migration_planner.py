"""
Migration Planner module for CNI Migration Tool

This module generates a step-by-step migration plan based on the cluster's configuration.
"""

import os
import logging
import yaml
import json
from datetime import datetime
from jinja2 import Template
from .k8s_utils import get_kubernetes_client, get_node_info, get_pod_cidr
from .assessment import detect_cni_type, count_network_policies

log = logging.getLogger("cni-migration.migration_planner")

# Templates for different migration approaches
HYBRID_TEMPLATE = """# Cilium Migration Plan - Hybrid Per-Node Approach

## Overview

This migration plan will guide you through migrating your Kubernetes cluster from {{ source_cni }} to Cilium using a hybrid per-node approach. This approach allows for a gradual migration with minimal disruption to running workloads.

In this approach, Cilium establishes a separate overlay network alongside the existing {{ source_cni }} network. Pods on each node will use either {{ source_cni }} or Cilium, but not both. However, pods can communicate across both networks during the migration process.

## Prerequisites

- Kubernetes cluster running {{ source_cni }} CNI version {{ cni_version }}
- kubectl access to the cluster with admin privileges
- Helm v3 (for Cilium deployment)
- Sufficient resources on nodes to run both CNIs temporarily
- A new, unused Pod CIDR range for Cilium

## Current Cluster Configuration

- Current CNI: {{ source_cni }} {{ cni_version }}
- Current Pod CIDR: {{ current_pod_cidr }}
- Number of nodes: {{ node_count }}
- Number of network policies: {{ policy_count }}

## Migration Steps

### 1. Prepare the Environment

1. **Backup your cluster configuration**
   ```bash
   kubectl get all --all-namespaces -o yaml > cluster-backup.yaml
   kubectl get networkpolicies --all-namespaces -o yaml > network-policies-backup.yaml
   {% if source_cni == 'calico' %}
   kubectl get crd | grep projectcalico.org | xargs -n1 -I{} sh -c "kubectl get {} --all-namespaces -o yaml > calico-{}.yaml"
   {% elif source_cni == 'cilium' %}
   kubectl get crd | grep cilium.io | xargs -n1 -I{} sh -c "kubectl get {} --all-namespaces -o yaml > cilium-{}.yaml"
   {% endif %}
   ```

2. **Deploy a connectivity validation tool**
   ```bash
   # Deploy a simple connectivity checker
   kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/{{ cilium_version }}/examples/kubernetes/connectivity-check/connectivity-check.yaml
   ```

3. **Verify current CNI functionality**
   ```bash
   # Check that all pods are running
   kubectl get pods --all-namespaces

   # Verify connectivity between pods
   kubectl exec -it $(kubectl get pods -l name=connectivity-check -o jsonpath='{.items[0].metadata.name}') -- curl -s connectivity-check:8080
   ```

### 2. Prepare Cilium Deployment

1. **Add the Cilium Helm repository**
   ```bash
   helm repo add cilium https://helm.cilium.io/
   helm repo update
   ```

2. **Create a Cilium configuration file (values.yaml)**
   ```yaml
   # values-migration.yaml
   ipam:
     mode: "cluster-pool"
     operator:
       clusterPoolIPv4PodCIDRList: ["{{ target_cidr }}"]
   tunnel: vxlan
   tunnelPort: 8473  # Use a different port than {{ source_cni }}
   cni:
     customConf: true  # Don't write CNI config initially
     uninstall: false  # Don't remove CNI configuration on shutdown
   operator:
     unmanagedPodWatcher:
       restart: false  # Don't restart unmigrated pods
   policyEnforcementMode: "never"  # Disable policy enforcement during migration
   bpf:
     hostLegacyRouting: true  # Allow for routing between Cilium and the existing overlay
   {% if source_cni == 'calico' %}
   # Additional settings for Calico migration
   hostPort:
     enabled: true
   hostServices:
     enabled: true
   {% endif %}
   {% if source_cni == 'aws-cni' %}
   # Additional settings for AWS VPC CNI migration
   eni:
     enabled: false
   {% endif %}
   ```

3. **Generate a complete Helm values file with auto-detected settings**
   ```bash
   # If using cilium CLI
   cilium install --helm-values values-migration.yaml --helm-auto-gen-values values-initial.yaml --dry-run

   # Or manually add cluster-specific settings
   ```

### 3. Deploy Cilium as a Secondary Overlay

1. **Install Cilium using Helm**
   ```bash
   helm install cilium cilium/cilium --namespace kube-system --values values-initial.yaml
   ```

2. **Verify Cilium is running but not managing any pods**
   ```bash
   # Wait for Cilium to be ready
   kubectl -n kube-system rollout status ds/cilium

   # Check Cilium status
   cilium status
   # Should show "Cluster Pods: 0/X managed by Cilium"
   ```

3. **Create the CiliumNodeConfig for per-node migration**
   ```bash
   cat <<EOF | kubectl apply --server-side -f -
   apiVersion: cilium.io/v2alpha1
   kind: CiliumNodeConfig
   metadata:
     namespace: kube-system
     name: cilium-default
   spec:
     nodeSelector:
       matchLabels:
         io.cilium.migration/cilium-default: "true"
     defaults:
       write-cni-conf-when-ready: /host/etc/cni/net.d/05-cilium.conflist
       custom-cni-conf: "false"
       cni-chaining-mode: "none"
       cni-exclusive: "true"
   EOF
   ```

### 4. Migrate Nodes One by One

For each node in your cluster, follow these steps:

1. **Cordon and drain the node**
   ```bash
   export NODE=<node-name>
   kubectl cordon $NODE
   kubectl drain --ignore-daemonsets --delete-emptydir-data $NODE
   ```

2. **Label the node to enable Cilium CNI**
   ```bash
   kubectl label node $NODE --overwrite "io.cilium.migration/cilium-default=true"
   ```

3. **Restart Cilium on the node**
   ```bash
   kubectl -n kube-system delete pod --field-selector spec.nodeName=$NODE -l k8s-app=cilium
   kubectl -n kube-system rollout status ds/cilium -w
   ```

4. **Reboot the node**
   ```bash
   # For cloud providers, use their specific node reboot commands
   # For on-premises clusters, SSH to the node and reboot
   # For kind/minikube, use docker restart or minikube ssh
   ```

5. **Verify the CNI configuration on the node**
   ```bash
   # For kind/minikube
   docker exec $NODE ls -la /etc/cni/net.d/

   # For other clusters, create a debug pod
   kubectl run debug-$NODE --overrides='{"spec": {"nodeName": "'$NODE'", "tolerations": [{"operator": "Exists"}]}}' --image=busybox --restart=Never -- sleep 3600
   kubectl exec debug-$NODE -- ls -la /etc/cni/net.d/

   # Should show:
   # - 05-cilium.conflist
   # - 10-{{ source_cni }}.conflist.cilium_bak
   ```

6. **Test connectivity from the migrated node**
   ```bash
   # Create a test pod on the migrated node
   kubectl run test-$NODE --overrides='{"spec": {"nodeName": "'$NODE'", "tolerations": [{"operator": "Exists"}]}}' --image=busybox --restart=Never -- sleep 3600

   # Verify it has a Cilium IP (from the new CIDR)
   kubectl exec test-$NODE -- ip addr

   # Test connectivity to a pod on an unmigrated node
   kubectl exec test-$NODE -- wget -qO- http://connectivity-check:8080
   ```

7. **Uncordon the node**
   ```bash
   kubectl uncordon $NODE
   ```

8. **Repeat for all nodes in the cluster**

### 5. Complete the Migration

Once all nodes have been migrated:

1. **Update Cilium configuration**
   ```bash
   # Create updated values file
   cilium install --helm-values values-initial.yaml --helm-set operator.unmanagedPodWatcher.restart=true --helm-set cni.customConf=false --helm-set policyEnforcementMode=default --helm-auto-gen-values values-final.yaml

   # Apply the updated configuration
   helm upgrade cilium cilium/cilium --namespace kube-system --values values-final.yaml

   # Restart Cilium
   kubectl -n kube-system rollout restart ds/cilium
   ```

2. **Delete the CiliumNodeConfig**
   ```bash
   kubectl delete -n kube-system ciliumnodeconfig cilium-default
   ```

3. **Uninstall {{ source_cni }}**
   {% if source_cni == 'calico' %}
   ```bash
   kubectl delete -f https://docs.projectcalico.org/v{{ cni_version }}/manifests/calico.yaml
   ```
   {% elif source_cni == 'flannel' %}
   ```bash
   kubectl delete -f https://raw.githubusercontent.com/flannel-io/flannel/v{{ cni_version }}/Documentation/kube-flannel.yml
   ```
   {% elif source_cni == 'weave' %}
   ```bash
   kubectl delete -f "https://cloud.weave.works/k8s/net?k8s-version=$(kubectl version | base64 | tr -d '\n')"
   ```
   {% else %}
   ```bash
   # Remove {{ source_cni }} manifests
   ```
   {% endif %}

4. **Clean up {{ source_cni }} resources**
   {% if source_cni == 'calico' %}
   ```bash
   # Remove Calico CRDs
   kubectl get crd | grep projectcalico.org | xargs -I{} kubectl delete crd {}

   # Clean up Calico iptables rules (run on each node)
   iptables-save -t nat | grep -oP '(?<!^:)cali-[^ ]+' | while read line; do iptables -t nat -F $line; done
   iptables-save -t raw | grep -oP '(?<!^:)cali-[^ ]+' | while read line; do iptables -t raw -F $line; done
   iptables-save -t mangle | grep -oP '(?<!^:)cali-[^ ]+' | while read line; do iptables -t mangle -F $line; done
   iptables-save -t filter | grep -oP '(?<!^:)cali-[^ ]+' | while read line; do iptables -t filter -F $line; done
   ```
   {% elif source_cni == 'flannel' %}
   ```bash
   # Remove flannel interfaces (run on each node)
   ip link delete flannel.1
   ```
   {% endif %}

5. **Optional: Reboot all nodes**
   This ensures all remnants of the old CNI are cleaned up.

### 6. Post-Migration Verification

1. **Verify Cilium status**
   ```bash
   cilium status
   # Should show "Cluster Pods: X/X managed by Cilium"
   ```

2. **Verify all pods are running**
   ```bash
   kubectl get pods --all-namespaces
   ```

3. **Test connectivity**
   ```bash
   # Test pod-to-pod connectivity
   kubectl exec -it $(kubectl get pods -l name=connectivity-check -o jsonpath='{.items[0].metadata.name}') -- curl -s connectivity-check:8080

   # Test pod-to-service connectivity
   kubectl exec -it $(kubectl get pods -l name=connectivity-check -o jsonpath='{.items[0].metadata.name}') -- curl -s kubernetes.default.svc
   ```

4. **Enable and test network policies**
   ```bash
   # Apply a test policy
   kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/{{ cilium_version }}/examples/kubernetes/connectivity-check/connectivity-check-policy.yaml

   # Verify policy enforcement
   cilium status
   ```

## Rollback Plan

If issues occur during migration, follow these steps to roll back:

### For Individual Node Rollback

1. **Remove the Cilium label from the node**
   ```bash
   kubectl label node $NODE io.cilium.migration/cilium-default-
   ```

2. **Restart the node's Cilium pod**
   ```bash
   kubectl -n kube-system delete pod --field-selector spec.nodeName=$NODE -l k8s-app=cilium
   ```

3. **Reboot the node**
   This will restore the original CNI configuration.

### For Complete Rollback

1. **Uninstall Cilium**
   ```bash
   helm uninstall cilium -n kube-system
   ```

2. **Reinstall {{ source_cni }}** (if already uninstalled)
   {% if source_cni == 'calico' %}
   ```bash
   kubectl apply -f https://docs.projectcalico.org/v{{ cni_version }}/manifests/calico.yaml
   ```
   {% elif source_cni == 'flannel' %}
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/v{{ cni_version }}/Documentation/kube-flannel.yml
   ```
   {% elif source_cni == 'weave' %}
   ```bash
   kubectl apply -f "https://cloud.weave.works/k8s/net?k8s-version=$(kubectl version | base64 | tr -d '\n')"
   ```
   {% else %}
   ```bash
   # Apply {{ source_cni }} manifests
   ```
   {% endif %}

3. **Reboot all nodes**
   This ensures the original CNI configuration is restored.

## Additional Resources

- [Cilium Documentation](https://docs.cilium.io/)
- [Cilium Migration Guide](https://docs.cilium.io/en/stable/installation/k8s-install-migration/)
- [Kubernetes CNI Documentation](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/)
- [Isovalent Migration Tutorial](https://isovalent.com/blog/post/tutorial-migrating-to-cilium-part-1/)

Generated on: {{ timestamp }}
"""

MULTUS_TEMPLATE = """# Cilium Migration Plan - Multus Multi-Interface Approach

## Overview

This migration plan will guide you through migrating your Kubernetes cluster from {{ source_cni }} to Cilium using the Multus CNI to attach multiple network interfaces during migration.

## Prerequisites

- Kubernetes cluster running {{ source_cni }} CNI
- kubectl access to the cluster
- Helm (if using Helm for deployment)
- Sufficient resources on nodes to run both CNIs

## Migration Steps

### 1. Prepare the Environment

1. Ensure you have a backup of your cluster configuration
2. Deploy Multus CNI:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/k8snetworkplumbingwg/multus-cni/master/deployments/multus-daemonset.yml
   ```

### 2. Deploy Cilium

1. Choose a new Pod CIDR for Cilium: `{{ target_cidr }}`
2. Install Cilium with the following configuration:
   ```yaml
   ipam:
     mode: "cluster-pool"
     operator:
       clusterPoolIPv4PodCIDRList: ["{{ target_cidr }}"]
   cni:
     exclusive: false
     chainingMode: "none"
   ```

### 3. Configure Multus

1. Create a ConfigMap for Multus with both CNIs:
   ```yaml
   kind: ConfigMap
   apiVersion: v1
   metadata:
     name: multus-cni-config
     namespace: kube-system
   data:
     cni-conf.json: |
       {
         "cniVersion": "0.3.1",
         "name": "multus-cni-network",
         "type": "multus",
         "capabilities": {
           "portMappings": true
         },
         "delegates": [
           {
             "cniVersion": "0.3.1",
             "name": "default-cni-network",
             "plugins": [
               {
                 "type": "{{ source_cni }}",
                 # {{ source_cni }}-specific configuration
               },
               {
                 "type": "portmap",
                 "snat": true,
                 "capabilities": {"portMappings": true}
               },
               {
                 "type": "sbr"
               }
             ]
           },
           {
             "cniVersion": "0.3.1",
             "name": "cilium",
             "type": "cilium-cni"
           }
         ],
         "kubeconfig": "/etc/cni/net.d/multus.d/multus.kubeconfig"
       }
   ```

### 4. Gradually Migrate Workloads

1. Annotate pods to use both CNIs:
   ```yaml
   annotations:
     k8s.v1.cni.cncf.io/networks: cilium
   ```

2. Restart pods to pick up the new configuration

### 5. Switch Primary CNI

1. Update the Multus ConfigMap to make Cilium the primary CNI:
   ```yaml
   delegates: [
     {
       "cniVersion": "0.3.1",
       "name": "default-cni-network",
       "type": "cilium-cni"
     },
     {
       "cniVersion": "0.3.1",
       "name": "{{ source_cni }}",
       # {{ source_cni }}-specific configuration
     }
   ]
   ```

2. Restart pods to use Cilium as the primary CNI

### 6. Remove Old CNI

1. Update the Multus ConfigMap to remove {{ source_cni }}
2. Uninstall {{ source_cni }}
3. Remove Multus when migration is complete

## Rollback Plan

If issues occur during migration, revert the Multus ConfigMap to use {{ source_cni }} as the primary CNI.

## Additional Resources

- [Multus CNI Documentation](https://github.com/k8snetworkplumbingwg/multus-cni)
- [Cilium Documentation](https://docs.cilium.io/)

Generated on: {{ timestamp }}
"""

CLEAN_TEMPLATE = """# Cilium Migration Plan - Clean Replacement Approach

## Overview

This migration plan will guide you through migrating your Kubernetes cluster from {{ source_cni }} to Cilium using a clean replacement approach. This approach requires downtime but is simpler to implement.

## Prerequisites

- Kubernetes cluster running {{ source_cni }} CNI
- kubectl access to the cluster
- Helm (if using Helm for deployment)
- Scheduled maintenance window for cluster downtime

## Migration Steps

### 1. Prepare the Environment

1. Ensure you have a backup of your cluster configuration
2. Schedule a maintenance window and notify users of the upcoming downtime
3. Prepare Cilium installation manifests

### 2. Perform the Migration

1. Cordon all nodes to prevent new workloads from being scheduled:
   ```bash
   kubectl cordon $(kubectl get nodes -o name | cut -d/ -f2)
   ```

2. Uninstall {{ source_cni }}:
   {% if source_cni == 'calico' %}
   ```bash
   kubectl delete -f https://docs.projectcalico.org/manifests/calico.yaml
   ```
   {% elif source_cni == 'flannel' %}
   ```bash
   kubectl delete -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
   ```
   {% else %}
   ```bash
   # Remove {{ source_cni }} manifests
   ```
   {% endif %}

3. Install Cilium:
   ```bash
   helm install cilium cilium/cilium --namespace kube-system \
     --set ipam.mode=cluster-pool \
     --set ipam.operator.clusterPoolIPv4PodCIDRList={"{{ target_cidr }}"}
   ```

4. Wait for Cilium to be ready:
   ```bash
   kubectl -n kube-system rollout status ds/cilium
   ```

5. Uncordon nodes:
   ```bash
   kubectl uncordon $(kubectl get nodes -o name | cut -d/ -f2)
   ```

6. Restart all pods to use Cilium networking:
   ```bash
   kubectl delete pods --all --all-namespaces
   ```

### 3. Verify the Migration

1. Verify Cilium status:
   ```bash
   cilium status
   ```

2. Verify all pods are running:
   ```bash
   kubectl get pods --all-namespaces
   ```

## Rollback Plan

If issues occur during migration, reinstall {{ source_cni }} and restart all pods.

## Additional Resources

- [Cilium Documentation](https://docs.cilium.io/)

Generated on: {{ timestamp }}
"""

def generate_migration_plan(target_cidr, approach, output_file):
    """
    Generate a step-by-step migration plan based on the cluster's configuration.

    Args:
        target_cidr (str): Target CIDR for Cilium
        approach (str): Migration approach to use (hybrid, multus, clean)
        output_file (str): Output file for migration plan

    Returns:
        bool: True if successful, False otherwise
    """
    log.info(f"Generating migration plan using {approach} approach")

    # Detect current CNI
    cni_info = detect_cni_type()
    source_cni = cni_info['cni_type']
    cni_version = cni_info['version'] or "latest"

    # Get additional cluster information
    api_client = get_kubernetes_client()
    core_v1 = client.CoreV1Api(api_client)

    # Get node count
    try:
        nodes = core_v1.list_node()
        node_count = len(nodes.items)
        log.info(f"Detected {node_count} nodes in the cluster")
    except Exception as e:
        log.warning(f"Error getting node count: {str(e)}")
        node_count = "unknown"

    # Get current Pod CIDR
    try:
        current_pod_cidr = get_pod_cidr()
        if not current_pod_cidr and 'details' in cni_info and 'pod_cidr' in cni_info['details']:
            current_pod_cidr = cni_info['details']['pod_cidr']
        log.info(f"Detected current Pod CIDR: {current_pod_cidr}")
    except Exception as e:
        log.warning(f"Error getting current Pod CIDR: {str(e)}")
        current_pod_cidr = "unknown"

    # Count network policies
    policy_info = count_network_policies()

    # Get latest Cilium version
    cilium_version = "v1.14.0"  # Default version
    try:
        import requests
        response = requests.get("https://api.github.com/repos/cilium/cilium/releases/latest")
        if response.status_code == 200:
            cilium_version = response.json()["tag_name"]
            log.info(f"Latest Cilium version: {cilium_version}")
    except Exception as e:
        log.warning(f"Error getting latest Cilium version: {str(e)}")

    # Select template based on approach
    if approach == 'hybrid':
        template_str = HYBRID_TEMPLATE
    elif approach == 'multus':
        template_str = MULTUS_TEMPLATE
    elif approach == 'clean':
        template_str = CLEAN_TEMPLATE
    else:
        raise ValueError(f"Unknown approach: {approach}")

    # Render template
    template = Template(template_str)
    plan = template.render(
        source_cni=source_cni,
        cni_version=cni_version,
        target_cidr=target_cidr,
        current_pod_cidr=current_pod_cidr,
        node_count=node_count,
        policy_count=policy_info['total'],
        cilium_version=cilium_version.lstrip('v'),  # Remove 'v' prefix for URLs
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # Write plan to file
    with open(output_file, 'w') as f:
        f.write(plan)

    log.info(f"Migration plan generated and saved to {output_file}")

    # Create a summary file with key information
    summary_file = f"{os.path.splitext(output_file)[0]}_summary.json"
    summary = {
        'source_cni': source_cni,
        'cni_version': cni_version,
        'target_cidr': target_cidr,
        'current_pod_cidr': current_pod_cidr,
        'node_count': node_count,
        'policy_count': policy_info['total'],
        'approach': approach,
        'cilium_version': cilium_version,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    log.info(f"Migration summary saved to {summary_file}")

    return True
