# Minikube Testing Framework

The CNI Migration Tool includes a comprehensive testing framework that uses Minikube to test the migration process in a real Kubernetes environment.

## Overview

The Minikube testing framework allows you to:

1. Set up Minikube clusters with different CNIs (Calico, Flannel, Weave)
2. Deploy test applications and network policies
3. Run the migration tool to migrate to Cilium
4. Validate the migration was successful

## Directory Structure

```
minikube/
├── README.md                     # Overview of the testing framework
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

## Prerequisites

- Minikube v1.30.0 or later
- kubectl v1.26.0 or later
- Docker or Podman
- Python 3.8+
- jq

## Running Tests

### Running a Complete Test

To run a complete test with Calico:

```bash
cd tests/minikube
./run-tests.sh --cni calico
```

### Setting Up a Specific CNI

To set up Minikube with a specific CNI:

```bash
cd tests/minikube
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
cd tests/minikube
./validation/connectivity-tests.sh
./validation/policy-tests.sh
```

## Test Scenarios

The testing framework includes the following test scenarios:

1. **Basic Migration**: Migrate from CNI X to Cilium with minimal configuration
2. **Policy Migration**: Migrate with network policies in place
3. **Cross-CNI Communication**: Test communication between pods during migration
4. **Rollback**: Test rollback procedure

## Test Applications

### Simple Test Pods

The testing framework includes simple test pods for basic connectivity testing:

- pod-a: A simple nginx pod
- pod-b: A simple nginx pod

### Microservices Demo

The testing framework also includes a more complex microservices demo application:

- Frontend: Serves as the entry point and forwards requests to the backend
- Backend: Processes requests and communicates with the database
- Database: Stores and retrieves data

## Network Policies

The testing framework includes sample network policies for both Kubernetes and Calico:

- default-deny: Deny all ingress and egress traffic
- allow-pod-a-to-pod-b: Allow traffic from pod-a to pod-b
- allow-dns: Allow DNS traffic

## Validation Tests

### Connectivity Tests

The connectivity tests check:

- Pod-to-pod connectivity
- Pod-to-service connectivity
- DNS resolution
- External connectivity

### Policy Tests

The policy tests check:

- Default deny policy enforcement
- Selective allow policy enforcement
- DNS policy enforcement

## Customizing Tests

### Adding New Test Applications

To add new test applications:

1. Create a new directory under `test-apps/`
2. Add Kubernetes manifests for your application
3. Update the validation scripts to test your application

### Adding New Network Policies

To add new network policies:

1. Create new policy files under `test-apps/network-policies/k8s/` or `test-apps/network-policies/calico/`
2. Update the validation scripts to test your policies

### Adding New Test Scenarios

To add new test scenarios:

1. Update the `run-tests.sh` script to include your new scenario
2. Add any necessary setup or validation scripts

## Troubleshooting

### Common Issues

- **Minikube fails to start**: Check that you have enough resources allocated to Minikube
- **CNI installation fails**: Check that you're using a compatible Kubernetes version
- **Connectivity tests fail**: Check that the CNI is properly installed and configured
- **Policy tests fail**: Check that the network policies are properly applied

### Collecting Logs

To collect logs for troubleshooting:

```bash
mkdir -p logs
kubectl get pods --all-namespaces -o wide > logs/pods.txt
kubectl get nodes -o wide > logs/nodes.txt
kubectl describe nodes > logs/nodes-describe.txt
kubectl get events --all-namespaces --sort-by='.metadata.creationTimestamp' > logs/events.txt
minikube logs > logs/minikube.txt
```
