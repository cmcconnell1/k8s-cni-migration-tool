# Minikube Testing Framework for CNI Migration Tool

This directory contains scripts and resources for testing the CNI Migration Tool in a real Kubernetes environment using Minikube.

## Overview

The testing framework allows you to:

1. Set up Minikube clusters with different CNI solutions (Calico, Flannel, Weave)
2. Deploy test applications and network policies
3. Run the migration tool to migrate to Cilium
4. Validate the migration was successful

## Prerequisites

- Minikube v1.30.0 or later
- kubectl v1.26.0 or later
- Docker or Podman
- Python 3.8+
- jq

## Directory Structure

```
minikube/
├── README.md                     # This file
├── setup/                        # Setup scripts for different CNIs
│   ├── setup-calico.sh           # Setup Minikube with Calico
│   ├── setup-flannel.sh          # Setup Minikube with Flannel
│   ├── setup-weave.sh            # Setup Minikube with Weave
│   └── setup-cilium.sh           # Setup Minikube with Cilium (for reference)
├── test-apps/                    # Test applications and manifests
│   ├── microservices-demo/       # Sample microservices application
│   └── network-policies/         # Sample network policies
│       ├── k8s/                  # Kubernetes NetworkPolicies
│       └── calico/               # Calico NetworkPolicies
├── validation/                   # Validation scripts and resources
│   ├── connectivity-tests.sh     # Test connectivity between pods
│   └── policy-tests.sh           # Test network policy enforcement
└── run-tests.sh                  # Main test runner script
```

## Usage

### Running a Complete Test

To run a complete test with Calico:

```bash
./run-tests.sh --cni calico
```

### Setting Up a Specific CNI

To set up Minikube with a specific CNI:

```bash
./setup/setup-calico.sh
```

### Deploying Test Applications

To deploy test applications and network policies:

```bash
kubectl apply -f test-apps/microservices-demo/
kubectl apply -f test-apps/network-policies/k8s/
```

### Running Validation Tests

To run validation tests:

```bash
./validation/connectivity-tests.sh
./validation/policy-tests.sh
```

## Test Scenarios

The testing framework includes the following test scenarios:

1. **Basic Migration**: Migrate from CNI X to Cilium with minimal configuration
2. **Policy Migration**: Migrate with network policies in place
3. **Cross-CNI Communication**: Test communication between pods during migration
4. **Rollback**: Test rollback procedure

## Adding New Tests

To add new test scenarios:

1. Create a new directory under `test-apps/` for your test application
2. Add Kubernetes manifests for your application
3. Add network policies under `test-apps/network-policies/`
4. Update the validation scripts to test your scenario
5. Update `run-tests.sh` to include your new test scenario
