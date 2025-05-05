#!/bin/bash
# Main test runner script for CNI Migration Tool

set -e

# Default values
CNI="calico"
KUBERNETES_VERSION="v1.26.0"
SKIP_SETUP=false
SKIP_VALIDATION=false
SKIP_MIGRATION=false
SKIP_CLEANUP=false
MIGRATION_APPROACH="hybrid"
TARGET_CIDR="10.245.0.0/16"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print section header
print_header() {
    echo -e "\n${GREEN}==== $1 ====${NC}\n"
}

# Print info message
print_info() {
    echo -e "${YELLOW}INFO: $1${NC}"
}

# Print error message
print_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

# Print success message
print_success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

# Print usage
print_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --cni <cni>              CNI to test (calico, flannel, weave) [default: calico]"
    echo "  --kubernetes-version <version>  Kubernetes version to use [default: v1.26.0]"
    echo "  --skip-setup             Skip setup phase"
    echo "  --skip-validation        Skip validation phase"
    echo "  --skip-migration         Skip migration phase"
    echo "  --skip-cleanup           Skip cleanup phase"
    echo "  --migration-approach <approach>  Migration approach (hybrid, multus, clean) [default: hybrid]"
    echo "  --target-cidr <cidr>     Target CIDR for Cilium [default: 10.245.0.0/16]"
    echo "  --help                   Show this help message"
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cni)
                CNI="$2"
                shift 2
                ;;
            --kubernetes-version)
                KUBERNETES_VERSION="$2"
                shift 2
                ;;
            --skip-setup)
                SKIP_SETUP=true
                shift
                ;;
            --skip-validation)
                SKIP_VALIDATION=true
                shift
                ;;
            --skip-migration)
                SKIP_MIGRATION=true
                shift
                ;;
            --skip-cleanup)
                SKIP_CLEANUP=true
                shift
                ;;
            --migration-approach)
                MIGRATION_APPROACH="$2"
                shift 2
                ;;
            --target-cidr)
                TARGET_CIDR="$2"
                shift 2
                ;;
            --help)
                print_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    # Validate CNI
    if [[ "$CNI" != "calico" && "$CNI" != "flannel" && "$CNI" != "weave" ]]; then
        print_error "Invalid CNI: $CNI. Must be one of: calico, flannel, weave"
        exit 1
    fi

    # Validate migration approach
    if [[ "$MIGRATION_APPROACH" != "hybrid" && "$MIGRATION_APPROACH" != "multus" && "$MIGRATION_APPROACH" != "clean" ]]; then
        print_error "Invalid migration approach: $MIGRATION_APPROACH. Must be one of: hybrid, multus, clean"
        exit 1
    fi
}

# Setup phase
setup_phase() {
    print_header "Setup Phase"

    if [ "$SKIP_SETUP" = true ]; then
        print_info "Skipping setup phase"
        return
    fi

    print_info "Setting up Minikube with $CNI CNI and Kubernetes $KUBERNETES_VERSION..."

    # Make setup script executable
    chmod +x ./setup/setup-$CNI.sh

    # Run setup script with Kubernetes version
    KUBERNETES_VERSION=$KUBERNETES_VERSION ./setup/setup-$CNI.sh

    print_success "Setup phase completed"
}

# Validation phase (pre-migration)
validation_pre_phase() {
    print_header "Pre-Migration Validation Phase"

    if [ "$SKIP_VALIDATION" = true ]; then
        print_info "Skipping pre-migration validation phase"
        return
    fi

    print_info "Running pre-migration validation tests..."

    # Make validation scripts executable
    chmod +x ./validation/connectivity-tests.sh
    chmod +x ./validation/policy-tests.sh

    # Run validation scripts
    ./validation/connectivity-tests.sh
    ./validation/policy-tests.sh

    print_success "Pre-migration validation phase completed"
}

# Apply network policies
apply_network_policies() {
    print_header "Applying Network Policies"

    if [ "$CNI" = "calico" ]; then
        print_info "Applying Calico network policies..."
        kubectl apply -f ./test-apps/network-policies/calico/
    else
        print_info "Applying Kubernetes network policies..."
        kubectl apply -f ./test-apps/network-policies/k8s/
    fi

    print_success "Network policies applied"
}

# Migration phase
migration_phase() {
    print_header "Migration Phase"

    if [ "$SKIP_MIGRATION" = true ]; then
        print_info "Skipping migration phase"
        return
    fi

    # Create output directories
    mkdir -p ../../assessment
    mkdir -p ../../converted-policies
    mkdir -p ../../validation-reports

    # Run assessment
    print_info "Running assessment..."
    cd ../..
    python cni_migration.py assess --output-dir ./assessment --debug

    # Convert network policies
    print_info "Converting network policies..."
    python cni_migration.py convert --source-cni $CNI --input-dir ./assessment/policies --output-dir ./converted-policies --validate --no-apply

    # Generate migration plan
    print_info "Generating migration plan..."
    python cni_migration.py plan --target-cidr $TARGET_CIDR --approach $MIGRATION_APPROACH --output-file ./migration-plan.md

    # Validate pre-migration connectivity
    print_info "Validating pre-migration connectivity..."
    python cni_migration.py validate --phase pre --report-dir ./validation-reports

    # Install Cilium
    print_info "Installing Cilium..."
    cd tests/minikube

    # Make Cilium setup script executable
    chmod +x ./setup/setup-cilium.sh

    # Run Cilium setup script
    ./setup/setup-cilium.sh

    # Validate during-migration connectivity
    print_info "Validating during-migration connectivity..."
    cd ../..
    python cni_migration.py validate --phase during --source-cni $CNI --target-cidr $TARGET_CIDR --report-dir ./validation-reports

    # Apply converted policies
    print_info "Applying converted policies..."
    kubectl apply -f ./converted-policies/k8s/
    if [ "$CNI" = "calico" ]; then
        kubectl apply -f ./converted-policies/calico/
    fi

    # Validate post-migration connectivity
    print_info "Validating post-migration connectivity..."
    python cni_migration.py validate --phase post --source-cni $CNI --report-dir ./validation-reports

    cd tests/minikube

    print_success "Migration phase completed"
}

# Cleanup phase
cleanup_phase() {
    print_header "Cleanup Phase"

    if [ "$SKIP_CLEANUP" = true ]; then
        print_info "Skipping cleanup phase"
        return
    fi

    print_info "Cleaning up Minikube..."

    # Stop Minikube
    minikube stop

    # Delete Minikube
    minikube delete

    print_success "Cleanup phase completed"
}

# Main function
main() {
    print_header "CNI Migration Tool Test Runner"

    # Parse command line arguments
    parse_args "$@"

    # Print test configuration
    print_info "Test configuration:"
    print_info "CNI: $CNI"
    print_info "Kubernetes version: $KUBERNETES_VERSION"
    print_info "Migration approach: $MIGRATION_APPROACH"
    print_info "Target CIDR: $TARGET_CIDR"
    print_info "Skip setup: $SKIP_SETUP"
    print_info "Skip validation: $SKIP_VALIDATION"
    print_info "Skip migration: $SKIP_MIGRATION"
    print_info "Skip cleanup: $SKIP_CLEANUP"

    # Run test phases
    setup_phase
    apply_network_policies
    validation_pre_phase
    migration_phase
    cleanup_phase

    print_header "Test Completed Successfully"
}

# Run main function
main "$@"
