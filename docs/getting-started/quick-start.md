# Quick Start

This guide will help you get started with the CNI Migration Tool and perform a basic migration from your current CNI to Cilium.

## Prerequisites

- Kubernetes cluster with admin access
- kubectl configured to access your cluster
- Python 3.8 or later

## Installation

Install the CNI Migration Tool using pip:

```bash
pip install k8s-cni-migration-tool
```

Or clone the repository and install from source:

```bash
git clone https://github.com/yourusername/k8s-cni-migration-tool.git
cd k8s-cni-migration-tool
pip install -e .
```

## Basic Usage

### 1. Assess Current CNI Configuration

First, assess your current CNI configuration to determine the migration difficulty:

```bash
cni-migration assess --output-dir ./assessment
```

This will create an assessment report in the `./assessment` directory.

### 2. Convert Network Policies

Convert your existing network policies to Cilium format:

```bash
cni-migration convert --source-cni calico --input-dir ./assessment/policies --output-dir ./converted-policies
```

Replace `calico` with your current CNI type.

### 3. Generate Migration Plan

Generate a step-by-step migration plan:

```bash
cni-migration plan --target-cidr 10.245.0.0/16 --approach hybrid --output-file ./migration-plan.md
```

Replace `10.245.0.0/16` with your desired target CIDR for Cilium.

### 4. Validate Connectivity

Validate connectivity before migration:

```bash
cni-migration validate --phase pre
```

### 5. Follow Migration Plan

Follow the steps in the generated migration plan to migrate your cluster to Cilium.

### 6. Validate Connectivity During Migration

Validate connectivity during migration:

```bash
cni-migration validate --phase during --source-cni calico --target-cidr 10.245.0.0/16
```

### 7. Validate Connectivity After Migration

Validate connectivity after migration:

```bash
cni-migration validate --phase post --source-cni calico
```

## Using the Migration Workflow Script

The tool provides a migration workflow script for easier usage:

```bash
# Navigate to the examples directory
cd examples

# Run the migration workflow script
bash migration_workflow.sh
```

This script will run all the steps in sequence and handle special cases like unknown or default CNIs.

## Next Steps

- Read the [User Guide](../user-guide/assessment.md) for more detailed information
- Learn about different [Migration Approaches](../approaches/hybrid.md)
- Check out the [API Reference](../api/assessment.md) for programmatic usage
