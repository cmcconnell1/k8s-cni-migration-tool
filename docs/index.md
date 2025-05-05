# CNI Migration Tool

A comprehensive tool to facilitate migration from various Kubernetes CNI solutions to Cilium.

## Overview

The CNI Migration Tool helps Kubernetes administrators assess their current CNI configuration, convert network policies, generate migration plans, and validate connectivity during the migration process.

![CNI Migration Tool](assets/cni-migration-tool.png)

## Features

- **Assessment**: Analyze current CNI configuration and determine migration difficulty
- **Policy Conversion**: Convert network policies from source CNI to Cilium format
- **Migration Planning**: Generate detailed migration plans based on cluster configuration
- **Validation**: Test connectivity and policy enforcement at different migration phases

## Supported CNIs

The tool supports migration from the following CNIs to Cilium:

- Calico
- Flannel
- Weave

## Migration Approaches

The tool supports multiple migration approaches:

- **Hybrid**: Gradually migrate nodes one by one with both CNIs running in parallel
- **Multus**: Use Multus to run multiple CNIs simultaneously
- **Clean**: Remove the existing CNI and install Cilium

## Getting Started

Check out the [Quick Start](getting-started/quick-start.md) guide to get started with the CNI Migration Tool.

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

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/cmcconnell1/k8s-cni-migration-tool/blob/main/LICENSE) file for details.
