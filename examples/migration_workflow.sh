#!/bin/bash
# Example workflow for migrating from Calico to Cilium
# This script demonstrates the complete workflow using the enhanced CNI Migration Tool

set -e

# Create directories for outputs
mkdir -p assessment
mkdir -p converted-policies
mkdir -p validation-reports

echo "Step 1: Assessing current CNI configuration..."
python ../cni_migration.py assess --output-dir ./assessment --debug

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

echo "Step 2: Converting network policies..."
python ../cni_migration.py convert --source-cni $SOURCE_CNI --input-dir ./assessment/policies --output-dir ./converted-policies --validate --no-apply

echo "Step 3: Generating migration plan..."
python ../cni_migration.py plan --target-cidr $TARGET_CIDR --approach hybrid --output-file ./migration-plan.md

echo "Step 4: Validating pre-migration connectivity..."
python ../cni_migration.py validate --phase pre --report-dir ./validation-reports

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
echo "   python ../cni_migration.py validate --phase during --source-cni $SOURCE_CNI --target-cidr $TARGET_CIDR"
echo "4. After completing the migration, validate with:"
echo "   python ../cni_migration.py validate --phase post --source-cni $SOURCE_CNI"
