# Roadmap

This document outlines the planned features and improvements for the CNI Migration Tool.

## Short-Term Goals (Next 3-6 Months)

### Multi-Node Cluster Support

- **Enhanced node management**: Improve handling of large multi-node clusters
- **Node grouping**: Allow migration of nodes in groups based on labels or other criteria
- **Parallel migration workflows**: Enable migrating multiple nodes simultaneously
- **Node-specific configurations**: Support different migration configurations for different node types

### Cloud Provider Support

- **AWS EKS integration**:
  - Support for AWS VPC CNI specifics
  - Integration with EKS managed node groups
  - Handling of AWS-specific networking constraints

- **GKE integration**:
  - Support for GKE's network policy implementation
  - Integration with GKE node pools
  - Handling of GCP VPC networking

- **AKS integration**:
  - Support for Azure CNI specifics
  - Integration with AKS node pools
  - Handling of Azure networking constraints

### Improved Testing Framework

- **Expanded test coverage**: Add more comprehensive test scenarios
- **Multi-CNI test environments**: Test migrations between more CNI combinations
- **Performance testing**: Measure migration performance and impact

## Medium-Term Goals (6-12 Months)

### Managed Kubernetes Distributions

- **OpenShift support**:
  - Integration with OpenShift SDN
  - Support for OpenShift security contexts
  - Handling of OpenShift-specific network policies

- **Rancher RKE/RKE2 support**:
  - Integration with Rancher networking
  - Support for Rancher cluster management

- **k3s support**:
  - Lightweight migration paths for edge deployments
  - Support for k3s networking specifics

### Advanced Features

- **Automated rollback mechanisms**:
  - Automatic detection of migration failures
  - One-click rollback to previous CNI
  - State preservation during rollbacks

- **Enhanced policy translation**:
  - Support for complex network policy scenarios
  - Advanced rule transformation
  - Policy equivalence validation

- **Cilium Hubble integration**:
  - Network flow visibility during migration
  - Policy effectiveness monitoring
  - Performance impact analysis

## Long-Term Goals (12+ Months)

### User Experience Improvements

- **Web UI for migration management**:
  - Visual representation of migration status
  - Interactive migration planning
  - Drag-and-drop policy management

- **Real-time monitoring**:
  - Live migration progress tracking
  - Network performance metrics
  - Policy enforcement verification

- **Comprehensive reporting**:
  - Detailed migration reports
  - Before/after comparison
  - Automated documentation generation

### Advanced Networking Support

- **IPv6 and dual-stack migrations**:
  - Support for IPv6-only and dual-stack environments
  - Address management during migration
  - Policy translation for IPv6

- **Service mesh integration**:
  - Coordinated migration with service mesh deployments
  - Integration with Istio, Linkerd, and other mesh solutions
  - Support for Cilium's service mesh capabilities

- **Multi-cluster migrations**:
  - Support for migrating interconnected clusters
  - Handling of cluster mesh scenarios
  - Cross-cluster policy management

## Contributing to the Roadmap

We welcome community input on our roadmap! If you have suggestions or would like to contribute to any of these initiatives, please:

1. Open an issue on our GitHub repository
2. Join the discussion in our community meetings
3. Submit pull requests for features you'd like to implement

The roadmap is a living document and will be updated based on community feedback and changing priorities.
