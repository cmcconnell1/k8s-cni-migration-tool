# Star Wars Demo for CNI Migration

> **Important Note**: This demo is based on the original [Star Wars Demo created by the Cilium authors](https://docs.cilium.io/en/stable/gettingstarted/demo/). The Star Wars application, concept, and policy examples are their intellectual property. We have adapted their demo specifically to showcase our CNI migration tool's capabilities.

This demo showcases the migration from Kubernetes NetworkPolicies to Cilium NetworkPolicies using a Star Wars-themed application. It demonstrates the enhanced capabilities of Cilium's network policies compared to standard Kubernetes NetworkPolicies.

## Overview

The demo uses a simple application with three components:

- **deathstar**: An HTTP service that provides landing services (2 replicas)
- **tiefighter**: A client service from the empire
- **xwing**: A client service from the alliance

The demo demonstrates:
1. Connectivity without any network policies
2. Connectivity with Kubernetes NetworkPolicies (L3/L4)
3. Migration from Kubernetes NetworkPolicies to Cilium NetworkPolicies
4. Connectivity with Cilium NetworkPolicies (L3/L4/L7)

## Prerequisites

- A running Kubernetes cluster (minikube, kind, etc.)
- Cilium installed (or use the `--install-cilium` flag)
- kubectl configured to access your cluster

## Running the Demo

```bash
# Navigate to the star-wars-demo directory
cd examples/star-wars-demo

# Run the demo with interactive prompts
./star-wars-migration-demo.sh

# Run without interactive prompts
./star-wars-migration-demo.sh --no-interactive

# Install Cilium if not already installed
./star-wars-migration-demo.sh --install-cilium

# Skip cleanup after the demo
./star-wars-migration-demo.sh --skip-cleanup

# Show help
./star-wars-migration-demo.sh --help
```

## Demo Components

### Application (http-sw-app.yaml)

The application consists of:
- A `deathstar` deployment with 2 replicas
- A `deathstar` service exposing port 80
- A `tiefighter` pod
- An `xwing` pod

### Kubernetes NetworkPolicy (k8s_l3_l4_policy.yaml)

This policy:
- Allows traffic from pods with label `org: empire` to the `deathstar` service
- Blocks all other traffic to the `deathstar` service
- Works at L3/L4 (IP and port level)

### Cilium NetworkPolicy (sw_l3_l4_l7_policy.yaml)

This policy:
- Allows only POST requests to `/v1/request-landing` from pods with label `org: empire`
- Blocks all other HTTP methods and paths
- Blocks all traffic from pods without the label `org: empire`
- Works at L3/L4/L7 (IP, port, and HTTP level)

## What You'll See

1. **No Policy**: All pods can communicate with the `deathstar` service
2. **Kubernetes NetworkPolicy**:
   - `tiefighter` can access the `deathstar` service (all HTTP methods)
   - `xwing` cannot access the `deathstar` service
3. **Cilium NetworkPolicy**:
   - `tiefighter` can only make POST requests to `/v1/request-landing`
   - `tiefighter` cannot make PUT requests to `/v1/exhaust-port`
   - `xwing` cannot access the `deathstar` service at all

## Key Takeaways

- Kubernetes NetworkPolicies can only filter based on IP and port (L3/L4)
- Cilium NetworkPolicies can filter based on HTTP methods and paths (L7)
- Our migration tool can convert Kubernetes NetworkPolicies to Cilium NetworkPolicies
- Cilium provides more fine-grained control over network traffic

## Credits and Attribution

This demo is based on the [Cilium Star Wars Demo](https://docs.cilium.io/en/stable/gettingstarted/demo/) created by the Cilium authors. All credit for the Star Wars application concept, container images, and policy examples belongs to them.

We have adapted their excellent demo specifically to showcase our CNI migration tool's capabilities. No claim of ownership or originality is made regarding the Star Wars demo concept, and we encourage users to check out the original Cilium documentation for more information about their powerful network policy capabilities.
