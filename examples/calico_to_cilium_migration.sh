#!/bin/bash
# Example script for migrating from Calico to Cilium
# This script demonstrates the workflow using the CNI Migration Tool

set -e

# Create directories for outputs
mkdir -p assessment
mkdir -p converted-policies

echo "Step 1: Assessing current CNI configuration..."
python $(dirname $0)/../cni_migration.py --debug assess --output-dir ./assessment

# Extract information from the assessment
SOURCE_CNI=$(jq -r '.cni_type' assessment/assessment.json)
echo "Detected CNI: $SOURCE_CNI"

# This script is specifically for Calico to Cilium migration
# If the detected CNI is unknown or not supported by the convert command, we'll proceed with Calico as the source
if [[ "$SOURCE_CNI" == "unknown" || "$SOURCE_CNI" == "kubenet" || "$SOURCE_CNI" == "kindnet" ]]; then
    echo "CNI type '$SOURCE_CNI' is not directly supported by the policy converter."
    echo "This script is for Calico to Cilium migration, so we'll use 'calico' as the source."
    SOURCE_CNI="calico"
elif [[ "$SOURCE_CNI" != "calico" ]]; then
    echo "Warning: Detected CNI is $SOURCE_CNI, but this script is designed for Calico to Cilium migration."
    echo "Do you want to continue using $SOURCE_CNI as the source? (y/n)"
    read -r response
    if [[ "$response" != "y" ]]; then
        echo "Using 'calico' as the source instead."
        SOURCE_CNI="calico"
    fi
fi

echo "Step 2: Converting network policies..."
python $(dirname $0)/../cni_migration.py --debug convert --source-cni $SOURCE_CNI --input-dir ./assessment/policies --output-dir ./converted-policies

echo "Step 3: Generating migration plan..."
python $(dirname $0)/../cni_migration.py --debug plan --target-cidr 10.245.0.0/16 --approach hybrid --output-file ./migration-plan.md

echo "Step 4: Validating pre-migration connectivity..."
python $(dirname $0)/../cni_migration.py --debug validate --phase pre

echo "Migration preparation complete!"
echo "Review the migration plan in migration-plan.md and follow the steps to complete the migration."
echo "After migrating each node, run the validation with --phase during"
echo "After completing the migration, run the validation with --phase post"
