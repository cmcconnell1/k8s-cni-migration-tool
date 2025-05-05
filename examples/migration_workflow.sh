#!/bin/bash
# Example workflow for migrating from Calico to Cilium
# This script demonstrates the complete workflow using the enhanced CNI Migration Tool

set -e

# Create directories for outputs
mkdir -p assessment
mkdir -p converted-policies
mkdir -p validation-reports

echo "Step 1: Assessing current CNI configuration..."
python $(dirname $0)/../cni_migration.py --debug assess --output-dir ./assessment

# Extract information from the assessment
SOURCE_CNI=$(jq -r '.cni_type' assessment/assessment.json)
CURRENT_POD_CIDR=$(jq -r '.details.pod_cidr // "10.244.0.0/16"' assessment/assessment.json)

# Calculate a new CIDR that doesn't overlap with the current one
# This is a simple example - in production, you'd want to choose a CIDR carefully
TARGET_CIDR="10.245.0.0/16"
if [[ "$CURRENT_POD_CIDR" == *"10.245"* ]]; then
    TARGET_CIDR="10.246.0.0/16"
fi

echo "Current CNI: $SOURCE_CNI"
echo "Current Pod CIDR: $CURRENT_POD_CIDR"
echo "Target CIDR for Cilium: $TARGET_CIDR"

# Check if CNI type is unknown or not supported by the convert command
if [[ "$SOURCE_CNI" == "unknown" || "$SOURCE_CNI" == "kubenet" || "$SOURCE_CNI" == "kindnet" ]]; then
    echo "CNI type '$SOURCE_CNI' is not directly supported by the policy converter."
    echo "Using 'calico' as the default for policy conversion since it has the most similar policy model to Kubernetes NetworkPolicies."
    SOURCE_CNI="calico"
fi

echo "Step 2: Converting network policies..."
python $(dirname $0)/../cni_migration.py --debug convert --source-cni $SOURCE_CNI --input-dir ./assessment/policies --output-dir ./converted-policies --validate --no-apply

echo "Step 3: Generating migration plan..."
python $(dirname $0)/../cni_migration.py --debug plan --target-cidr $TARGET_CIDR --approach hybrid --output-file ./migration-plan.md

echo "Step 4: Validating pre-migration connectivity..."
python $(dirname $0)/../cni_migration.py --debug validate --phase pre --report-dir ./validation-reports

echo "Migration preparation complete!"
echo "Review the following files:"
echo "- Assessment report: assessment/assessment_report.md"
echo "- Converted policies: converted-policies/conversion_report.md"
echo "- Migration plan: migration-plan.md"
echo "- Pre-migration validation: validation-reports/"

echo ""
echo "Next steps:"
echo "1. Review the migration plan in migration-plan.md"
echo "2. Follow the steps in the migration plan to deploy Cilium"
echo "3. During migration, validate connectivity with:"
echo "   python $(dirname $0)/../cni_migration.py --debug validate --phase during --source-cni $SOURCE_CNI --target-cidr $TARGET_CIDR"
echo "4. After completing the migration, validate with:"
echo "   python $(dirname $0)/../cni_migration.py --debug validate --phase post --source-cni $SOURCE_CNI"
echo ""
echo "Note: The detected CNI type was '$SOURCE_CNI'. If this is incorrect, please specify the correct CNI type when running the commands."
