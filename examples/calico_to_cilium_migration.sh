#!/bin/bash
# Example script for migrating from Calico to Cilium
# This script demonstrates the workflow using the CNI Migration Tool

set -e

# Create directories for outputs
mkdir -p assessment
mkdir -p converted-policies

echo "Step 1: Assessing current CNI configuration..."
python ../cni_migration.py assess --output-dir ./assessment

echo "Step 2: Converting network policies..."
python ../cni_migration.py convert --source-cni calico --input-dir ./assessment/policies --output-dir ./converted-policies

echo "Step 3: Generating migration plan..."
python ../cni_migration.py plan --target-cidr 10.245.0.0/16 --approach hybrid --output-file ./migration-plan.md

echo "Step 4: Validating pre-migration connectivity..."
python ../cni_migration.py validate --phase pre

echo "Migration preparation complete!"
echo "Review the migration plan in migration-plan.md and follow the steps to complete the migration."
echo "After migrating each node, run the validation with --phase during"
echo "After completing the migration, run the validation with --phase post"
