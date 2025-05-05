# Kubernetes CNI Migration Tool
- A POC comprehensive tool for assessing and facilitating migration from existing Kubernetes CNI solutions (Flannel, Calico, Weave, etc.) to Cilium.
- Author: Chris McConnell @cmcconnell1

## Features

- **Assessment**: Analyze your current CNI configuration and determine migration difficulty
- **Policy Translation**: Convert existing network policies to Cilium-compatible format
- **Migration Planning**: Generate a step-by-step migration plan based on your cluster's specific configuration
- **Validation**: Verify connectivity and policy enforcement before, during, and after migration

## Why Migrate to Cilium?

Cilium provides several advantages over other CNI solutions:

- **eBPF-based**: Uses Linux kernel's eBPF technology for improved performance and security
- **Advanced Network Policies**: Supports L7 policies (HTTP, gRPC, Kafka)
- **Observability**: Integrated with Hubble for network flow visibility
- **Service Mesh**: Native service mesh capabilities without sidecars
- **Gateway API**: Native implementation of Kubernetes Gateway API
- **Scalability**: Better performance at scale compared to iptables-based solutions

## Prerequisites

- Python 3.8+ (Python 3.12 recommended)
- kubectl with access to your Kubernetes cluster
- Kubernetes cluster running one of the supported CNIs (Calico, Flannel, Weave)
- Cilium CLI (optional, for validation)

For testing with Minikube:
- Minikube v1.30.0 or later
- Docker or Podman
- jq (for parsing JSON output)

**Note:** If you're using Python 3.13, you might encounter compatibility issues with some dependencies. We recommend using Python 3.12 for the best experience.

## Installation

```bash
# clone the repository and install from source
git clone https://github.com/cmcconnell1/k8s-cni-migration-tool.git
cd k8s-cni-migration-tool

# Create a virtual environment (recommended)
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

# Install the package
pip install -e .
```

For development setup and troubleshooting, see the [Development Guide](DEVELOPMENT.md).

## Usage

### Running the Migration Workflow

The simplest way to use the tool is to run the migration workflow script directly:

```bash
# Set up a Python virtual environment
python3.12 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run the complete migration workflow script
cd examples
bash migration_workflow.sh
```

This script will:
1. Assess your current CNI configuration
2. Convert network policies to Cilium format
3. Generate a migration plan
4. Validate connectivity before migration

The results will be saved in the examples directory for review.

### Using the CLI Directly

For more control, you can use the CLI directly with individual commands:

```bash
# Make sure your virtual environment is activated
source .venv/bin/activate

# Assess current CNI configuration
python cni_migration.py --debug assess --output-dir ./assessment

# Convert network policies with validation
# Note: If your CNI is detected as 'kubenet' or 'kindnet', use 'calico' as the source-cni
python cni_migration.py --debug convert --source-cni calico --input-dir ./assessment/policies --output-dir ./converted-policies --validate --no-apply

# Generate migration plan
python cni_migration.py --debug plan --target-cidr 10.245.0.0/16 --approach hybrid --output-file ./migration-plan.md

# Validate connectivity (pre-migration)
python cni_migration.py --debug validate --phase pre --report-dir ./validation-reports

# Validate connectivity (during migration)
python cni_migration.py --debug validate --phase during --source-cni calico --target-cidr 10.245.0.0/16 --report-dir ./validation-reports

# Validate connectivity (post-migration)
python cni_migration.py --debug validate --phase post --source-cni calico --report-dir ./validation-reports
```

> **Important:** Note that the `--debug` flag is a global option and should be placed before the command (e.g., `assess`, `convert`, etc.).

### Example Workflow Script

The `examples/migration_workflow.sh` script demonstrates the complete migration process and handles special cases like unknown or default CNIs:

```bash
# Make sure your virtual environment is activated
source .venv/bin/activate

# Navigate to the examples directory
cd examples

# Run the example workflow
bash migration_workflow.sh
```

This script will:
1. Detect your CNI type automatically
2. Handle special cases like kubenet or kindnet by using calico as the source CNI for policy conversion
3. Generate all necessary files for migration
4. Provide next steps for completing the migration

## Migration Approaches

The tool supports multiple migration approaches:

### 1. Hybrid Per-Node Migration (Recommended)

This approach allows for a gradual migration with minimal disruption:

- Deploy Cilium alongside the existing CNI
- Migrate nodes one by one using Cilium's per-node configuration feature
- Maintain connectivity between pods on different CNIs during migration
- No cluster-wide downtime required

### 2. Multus Multi-Interface

This approach uses Multus CNI to attach multiple network interfaces:

- Deploy Multus CNI and configure it to use both the existing CNI and Cilium
- Pods can have interfaces from both CNIs simultaneously
- Gradually transition from the old CNI to Cilium
- More complex setup but allows for flexible migration

### 3. Clean Replacement

This approach is simpler but requires downtime:

- Schedule a maintenance window
- Remove the existing CNI
- Install Cilium
- Restart all pods to use Cilium networking

## Tool Components

- **Assessment Module**: Detects current CNI, counts network policies, and evaluates migration difficulty
  - Identifies CNI type, version, and configuration details
  - Analyzes network policies and their complexity
  - Provides a detailed assessment report with migration recommendations

- **Policy Converter**: Translates network policies to Cilium format
  - Converts Kubernetes NetworkPolicies to CiliumNetworkPolicies
  - Converts Calico NetworkPolicies to CiliumNetworkPolicies
  - Validates converted policies for correctness
  - Generates detailed conversion reports
  - Optionally applies converted policies to the cluster

- **Migration Planner**: Generates detailed migration plans
  - Creates step-by-step migration instructions based on cluster configuration
  - Supports multiple migration approaches (hybrid, multus, clean)
  - Includes rollback procedures and verification steps
  - Customizes plans based on source CNI and target configuration

- **Validator**: Tests connectivity and policy enforcement
  - Validates connectivity before, during, and after migration
  - Tests cross-CNI communication during migration
  - Verifies network policy enforcement
  - Generates detailed validation reports with recommendations

## Related Documentation

For more information about Kubernetes CNIs and migration strategies, check out these resources:

- [Kubernetes Networking and CNI Documentation](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
- [CNI Specification](https://github.com/containernetworking/cni/blob/master/SPEC.md)
- [Cilium CNI Migration Guide](https://docs.cilium.io/en/stable/installation/k8s-install-migration/)

Additional detailed documentation from the original project:

- [Kubernetes CNI Comparison](https://github.com/cmcconnell1/consulting-resources/blob/main/k8s-cni-comparison.md)
- [Kubernetes CNI Solutions Detail](https://github.com/cmcconnell1/consulting-resources/blob/main/k8s-cni-solutions-detail.md)
- [Kubernetes CNI Migration Paths](https://github.com/cmcconnell1/consulting-resources/blob/main/k8s-cni-migration-paths.md)

## External Resources

- [Cilium Documentation](https://docs.cilium.io/)
- [Cilium Migration Guide](https://docs.cilium.io/en/stable/installation/k8s-install-migration/)
- [Isovalent Migration Tutorial](https://isovalent.com/blog/post/tutorial-migrating-to-cilium-part-1/)

## Roadmap

The following features and improvements are planned for future releases:

### Multi-Node Cluster Support
- Enhanced support for large multi-node clusters
- Node-specific migration strategies
- Parallel migration workflows for faster migrations

### Cloud Provider Support
- AWS EKS-specific migration paths
- GKE-specific migration paths
- AKS-specific migration paths
- Support for cloud provider CNI integrations (VPC CNI, GKE CNI, etc.)

### Managed Kubernetes Distributions
- OpenShift migration support
- Rancher RKE/RKE2 migration support
- k3s migration support

### Advanced Features
- Automated rollback mechanisms
- Enhanced policy translation for complex scenarios
- Integration with Cilium Hubble for migration observability
- Support for IPv6 and dual-stack migrations

### User Experience
- Web UI for migration management
- Real-time migration status monitoring
- Comprehensive reporting and documentation generation

## Testing with Minikube

The tool includes scripts to set up and test migrations in a Minikube environment:

```bash
# Start Minikube with default CNI (kubenet/kindnet)
minikube start

# Or set up Minikube with a specific CNI
./tests/minikube/setup/setup-calico.sh  # For Calico
./tests/minikube/setup/setup-flannel.sh # For Flannel
./tests/minikube/setup/setup-weave.sh   # For Weave

# Run a complete test workflow
cd tests/minikube
./run-tests.sh --cni calico  # If using Calico
# Or for default CNI
./run-tests.sh --cni kubenet
```

> **Note:** Minikube uses kubenet (also called kindnet in newer versions) as its default CNI. The tool will detect this and use calico as the source CNI for policy conversion, as kubenet only supports standard Kubernetes NetworkPolicies.

The setup scripts will check if Minikube is installed but will not automatically install it. If Minikube is not found, you'll need to install it manually following the [Minikube installation guide](https://minikube.sigs.k8s.io/docs/start/).

For more details on Minikube testing, see the [Minikube Testing documentation](docs/testing/minikube.md).

## License

MIT
