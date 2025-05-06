#!/bin/bash
# Example workflow for migrating from any CNI to Cilium
# This script demonstrates the complete workflow using the enhanced CNI Migration Tool

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default values
OUTPUT_DIR="."
DEBUG=true
FORCE_CNI=""
TARGET_CIDR=""
APPROACH="hybrid"
SKIP_VALIDATION=false

# Function to print usage information
print_usage() {
    echo -e "${BOLD}Usage:${NC} $0 [OPTIONS]"
    echo ""
    echo "This script runs the complete CNI migration workflow from assessment to planning."
    echo ""
    echo -e "${BOLD}Options:${NC}"
    echo "  --output-dir DIR       Directory to store all output files (default: current directory)"
    echo "  --force-cni TYPE       Force a specific CNI type instead of auto-detection"
    echo "                         Supported types: calico, flannel, weave, cilium, kubenet, kindnet"
    echo "  --target-cidr CIDR     Specify target CIDR for Cilium (default: auto-calculated)"
    echo "  --approach TYPE        Migration approach: hybrid, clean, or canary (default: hybrid)"
    echo "  --skip-validation      Skip the pre-migration validation step"
    echo "  --no-debug             Disable debug output"
    echo "  --help                 Display this help message and exit"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  $0 --output-dir ./migration-results"
    echo "  $0 --force-cni calico --target-cidr 10.245.0.0/16"
    echo "  $0 --approach clean --skip-validation"
    echo ""
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --output-dir=*)
                OUTPUT_DIR="${1#*=}"
                shift
                ;;
            --force-cni)
                FORCE_CNI="$2"
                shift 2
                ;;
            --force-cni=*)
                FORCE_CNI="${1#*=}"
                shift
                ;;
            --target-cidr)
                TARGET_CIDR="$2"
                shift 2
                ;;
            --target-cidr=*)
                TARGET_CIDR="${1#*=}"
                shift
                ;;
            --approach)
                APPROACH="$2"
                shift 2
                ;;
            --approach=*)
                APPROACH="${1#*=}"
                shift
                ;;
            --skip-validation)
                SKIP_VALIDATION=true
                shift
                ;;
            --no-debug)
                DEBUG=false
                shift
                ;;
            --help)
                print_usage
                exit 0
                ;;
            *)
                echo "Error: Unknown option $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

# Parse command line arguments
parse_args "$@"

# Create directories for outputs
mkdir -p $OUTPUT_DIR/assessment
mkdir -p $OUTPUT_DIR/converted-policies
mkdir -p $OUTPUT_DIR/validation-reports

# Function to print section headers
print_section() {
    echo -e "\n${BLUE}${BOLD}=== $1 ===${NC}\n"
}

# Set debug flag
DEBUG_FLAG=""
if [ "$DEBUG" = true ]; then
    DEBUG_FLAG="--debug"
fi

print_section "Step 1: Assessing current CNI configuration"
echo -e "${YELLOW}Running assessment to detect current CNI and network policies...${NC}"

# Run assessment
python $(dirname $0)/../cni_migration.py $DEBUG_FLAG assess --output-dir $OUTPUT_DIR/assessment

# Extract information from the assessment
SOURCE_CNI=$(jq -r '.cni_type' $OUTPUT_DIR/assessment/assessment.json)
CURRENT_POD_CIDR=$(jq -r '.details.pod_cidr // "10.244.0.0/16"' $OUTPUT_DIR/assessment/assessment.json)

# Use forced CNI if specified
if [ -n "$FORCE_CNI" ]; then
    echo -e "${YELLOW}Forcing CNI type to '$FORCE_CNI' instead of detected '$SOURCE_CNI'${NC}"
    SOURCE_CNI=$FORCE_CNI
fi

# Calculate a new CIDR that doesn't overlap with the current one if not specified
if [ -z "$TARGET_CIDR" ]; then
    TARGET_CIDR="10.245.0.0/16"
    if [[ "$CURRENT_POD_CIDR" == *"10.245"* ]]; then
        TARGET_CIDR="10.246.0.0/16"
    fi
    echo -e "${YELLOW}Auto-calculated target CIDR: $TARGET_CIDR${NC}"
else
    echo -e "${YELLOW}Using specified target CIDR: $TARGET_CIDR${NC}"
fi

echo -e "${GREEN}Current CNI:${NC} $SOURCE_CNI"
echo -e "${GREEN}Current Pod CIDR:${NC} $CURRENT_POD_CIDR"
echo -e "${GREEN}Target CIDR for Cilium:${NC} $TARGET_CIDR"

# Check if CNI type is unknown or not supported by the convert command
if [[ "$SOURCE_CNI" == "unknown" || "$SOURCE_CNI" == "kubenet" || "$SOURCE_CNI" == "kindnet" ]]; then
    echo -e "${YELLOW}CNI type '$SOURCE_CNI' is not directly supported by the policy converter.${NC}"
    echo -e "${YELLOW}Using 'calico' as the default for policy conversion since it has the most similar policy model to Kubernetes NetworkPolicies.${NC}"
    SOURCE_CNI="calico"
fi

print_section "Step 2: Converting network policies"
echo -e "${YELLOW}Converting network policies from $SOURCE_CNI to Cilium format...${NC}"

python $(dirname $0)/../cni_migration.py $DEBUG_FLAG convert --source-cni $SOURCE_CNI \
    --input-dir $OUTPUT_DIR/assessment/policies \
    --output-dir $OUTPUT_DIR/converted-policies \
    --validate --no-apply

print_section "Step 3: Generating migration plan"
echo -e "${YELLOW}Generating migration plan with $APPROACH approach...${NC}"

python $(dirname $0)/../cni_migration.py $DEBUG_FLAG plan \
    --target-cidr $TARGET_CIDR \
    --approach $APPROACH \
    --output-file $OUTPUT_DIR/migration-plan.md

# Only run validation if not skipped
if [ "$SKIP_VALIDATION" = false ]; then
    print_section "Step 4: Validating pre-migration connectivity"
    echo -e "${YELLOW}Running pre-migration connectivity validation...${NC}"

    python $(dirname $0)/../cni_migration.py $DEBUG_FLAG validate \
        --phase pre \
        --report-dir $OUTPUT_DIR/validation-reports
else
    echo -e "${YELLOW}Skipping pre-migration validation as requested.${NC}"
fi

print_section "Migration Preparation Complete"
echo -e "${GREEN}Migration preparation completed successfully!${NC}"
echo -e "\n${BOLD}Review the following files:${NC}"
echo -e "- Assessment report: ${YELLOW}$OUTPUT_DIR/assessment/assessment_report.md${NC}"
echo -e "- Converted policies: ${YELLOW}$OUTPUT_DIR/converted-policies/conversion_report.md${NC}"
echo -e "- Migration plan: ${YELLOW}$OUTPUT_DIR/migration-plan.md${NC}"
if [ "$SKIP_VALIDATION" = false ]; then
    echo -e "- Pre-migration validation: ${YELLOW}$OUTPUT_DIR/validation-reports/${NC}"
fi

echo -e "\n${BOLD}Next steps:${NC}"
echo -e "${GREEN}1.${NC} Review the migration plan in ${YELLOW}$OUTPUT_DIR/migration-plan.md${NC}"
echo -e "${GREEN}2.${NC} Follow the steps in the migration plan to deploy Cilium"
echo -e "${GREEN}3.${NC} During migration, validate connectivity with:"
echo -e "   ${YELLOW}python $(dirname $0)/../cni_migration.py $DEBUG_FLAG validate --phase during --source-cni $SOURCE_CNI --target-cidr $TARGET_CIDR --report-dir $OUTPUT_DIR/validation-reports${NC}"
echo -e "${GREEN}4.${NC} After completing the migration, validate with:"
echo -e "   ${YELLOW}python $(dirname $0)/../cni_migration.py $DEBUG_FLAG validate --phase post --source-cni $SOURCE_CNI --report-dir $OUTPUT_DIR/validation-reports${NC}"

echo -e "\n${BOLD}Note:${NC} The CNI type used for conversion was '${YELLOW}$SOURCE_CNI${NC}'."
if [ -z "$FORCE_CNI" ] && [[ "$SOURCE_CNI" == "calico" ]] && [[ "$SOURCE_CNI" != $(jq -r '.cni_type' $OUTPUT_DIR/assessment/assessment.json) ]]; then
    echo -e "This was automatically selected because the detected CNI '$(jq -r '.cni_type' $OUTPUT_DIR/assessment/assessment.json)' is not directly supported."
    echo -e "If this is incorrect, re-run with ${YELLOW}--force-cni TYPE${NC} to specify the correct CNI type."
fi

echo -e "\n${BOLD}To run the next validation steps:${NC}"
echo -e "${YELLOW}cd $(dirname $0)${NC}"
echo -e "${YELLOW}./migration_workflow.sh --help${NC} # For more options"
