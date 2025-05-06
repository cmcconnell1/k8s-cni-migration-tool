#!/bin/bash
# Star Wars Demo for CNI Migration
# This script demonstrates the migration from Kubernetes NetworkPolicies to Cilium NetworkPolicies
# using the Star Wars demo application
#
# ATTRIBUTION NOTE:
# This demo is based on the original Star Wars Demo created by the Cilium authors:
# https://docs.cilium.io/en/stable/gettingstarted/demo/
#
# All credit for the Star Wars application concept, container images, and policy examples
# belongs to the Cilium team. We have adapted their excellent demo to showcase our
# CNI migration tool's capabilities.

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default values
INTERACTIVE=true
SKIP_CLEANUP=false
INSTALL_CILIUM=false

# Function to print section headers
print_section() {
    echo -e "\n${BLUE}${BOLD}=== $1 ===${NC}\n"
}

# Function to wait for user input in interactive mode
wait_for_user() {
    if [ "$INTERACTIVE" = true ]; then
        echo -e "\n${YELLOW}Press Enter to continue...${NC}"
        read -r
    fi
}

# Function to print connectivity results
print_connectivity_result() {
    local from=$1
    local to=$2
    local result=$3

    if [ "$result" -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} $from → $to: ${GREEN}Connected${NC}"
    else
        echo -e "  ${RED}✗${NC} $from → $to: ${RED}Blocked${NC}"
    fi
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-interactive)
                INTERACTIVE=false
                shift
                ;;
            --skip-cleanup)
                SKIP_CLEANUP=true
                shift
                ;;
            --install-cilium)
                INSTALL_CILIUM=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --no-interactive     Run without interactive prompts"
                echo "  --skip-cleanup       Don't clean up resources after running"
                echo "  --install-cilium     Install Cilium if not already installed"
                echo "  --help               Show this help message"
                exit 0
                ;;
            *)
                echo "Error: Unknown option $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# Check if minikube is running
check_minikube() {
    print_section "Checking Minikube"
    echo -e "${YELLOW}Checking if minikube is running...${NC}"

    if ! minikube status | grep -q "Running"; then
        echo -e "${RED}Minikube is not running. Please start minikube first.${NC}"
        exit 1
    fi

    echo -e "${GREEN}Minikube is running.${NC}"
    wait_for_user
}

# Check if Cilium is installed
check_cilium() {
    print_section "Checking Cilium"
    echo -e "${YELLOW}Checking if Cilium is installed...${NC}"

    if ! kubectl get pods -n kube-system -l k8s-app=cilium 2>/dev/null | grep -q cilium; then
        echo -e "${RED}Cilium is not installed.${NC}"

        if [ "$INSTALL_CILIUM" = true ]; then
            echo -e "${YELLOW}Installing Cilium...${NC}"
            # Install Cilium using Helm
            helm repo add cilium https://helm.cilium.io/
            helm install cilium cilium/cilium --namespace kube-system

            # Wait for Cilium to be ready
            echo -e "${YELLOW}Waiting for Cilium to be ready...${NC}"
            kubectl wait --for=condition=ready pod -l k8s-app=cilium -n kube-system --timeout=120s

            echo -e "${GREEN}Cilium installed successfully.${NC}"
        else
            echo -e "${YELLOW}Use --install-cilium to install Cilium automatically.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}Cilium is installed.${NC}"
    fi

    wait_for_user
}

# Deploy the Star Wars demo application
deploy_demo_app() {
    print_section "Deploying Star Wars Demo Application"
    echo -e "${YELLOW}Deploying the Star Wars demo application...${NC}"

    kubectl apply -f http-sw-app.yaml

    # Wait for pods to be ready
    echo -e "${YELLOW}Waiting for pods to be ready...${NC}"
    kubectl wait --for=condition=ready pod/tiefighter --timeout=60s
    kubectl wait --for=condition=ready pod/xwing --timeout=60s
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=deathstar --timeout=60s

    echo -e "${GREEN}Star Wars demo application deployed successfully.${NC}"
    wait_for_user
}

# Test connectivity without any policies
test_connectivity_no_policy() {
    print_section "Testing Connectivity (No Policies)"
    echo -e "${YELLOW}Testing connectivity without any policies...${NC}"

    # Test tiefighter to deathstar connectivity
    echo -e "\n${BOLD}Testing tiefighter to deathstar connectivity:${NC}"
    kubectl exec tiefighter -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing > /dev/null
    print_connectivity_result "tiefighter" "deathstar (POST /v1/request-landing)" $?

    kubectl exec tiefighter -- curl -s -XPUT deathstar.default.svc.cluster.local/v1/exhaust-port > /dev/null
    print_connectivity_result "tiefighter" "deathstar (PUT /v1/exhaust-port)" $?

    # Test xwing to deathstar connectivity
    echo -e "\n${BOLD}Testing xwing to deathstar connectivity:${NC}"
    kubectl exec xwing -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing > /dev/null
    print_connectivity_result "xwing" "deathstar (POST /v1/request-landing)" $?

    echo -e "\n${BOLD}Summary:${NC}"
    echo -e "  All connections are ${GREEN}allowed${NC} without any network policies."

    wait_for_user
}

# Apply Kubernetes NetworkPolicy
apply_k8s_policy() {
    print_section "Applying Kubernetes NetworkPolicy"
    echo -e "${YELLOW}Applying Kubernetes NetworkPolicy...${NC}"

    kubectl apply -f k8s_l3_l4_policy.yaml

    echo -e "${GREEN}Kubernetes NetworkPolicy applied.${NC}"
    echo -e "${YELLOW}Waiting for policy to take effect...${NC}"
    sleep 5

    wait_for_user
}

# Test connectivity with Kubernetes NetworkPolicy
test_connectivity_k8s_policy() {
    print_section "Testing Connectivity (Kubernetes NetworkPolicy)"
    echo -e "${YELLOW}Testing connectivity with Kubernetes NetworkPolicy...${NC}"

    # Test tiefighter to deathstar connectivity
    echo -e "\n${BOLD}Testing tiefighter to deathstar connectivity:${NC}"
    kubectl exec tiefighter -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing > /dev/null
    print_connectivity_result "tiefighter" "deathstar (POST /v1/request-landing)" $?

    kubectl exec tiefighter -- curl -s -XPUT deathstar.default.svc.cluster.local/v1/exhaust-port > /dev/null
    print_connectivity_result "tiefighter" "deathstar (PUT /v1/exhaust-port)" $?

    # Test xwing to deathstar connectivity
    echo -e "\n${BOLD}Testing xwing to deathstar connectivity:${NC}"
    kubectl exec xwing -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing > /dev/null
    print_connectivity_result "xwing" "deathstar (POST /v1/request-landing)" $?

    echo -e "\n${BOLD}Summary:${NC}"
    echo -e "  Kubernetes NetworkPolicy allows all traffic from tiefighter to deathstar"
    echo -e "  Kubernetes NetworkPolicy blocks all traffic from xwing to deathstar"
    echo -e "  Kubernetes NetworkPolicy cannot filter based on HTTP methods or paths"

    wait_for_user
}

# Run the migration tool
run_migration_tool() {
    print_section "Running CNI Migration Tool"
    echo -e "${YELLOW}Running the CNI migration tool...${NC}"

    # Create directories for outputs
    mkdir -p assessment
    mkdir -p converted-policies

    # Run the assessment
    echo -e "${YELLOW}Running assessment...${NC}"
    python ../../cni_migration.py --debug assess --output-dir ./assessment

    # Convert policies
    echo -e "${YELLOW}Converting policies...${NC}"
    python ../../cni_migration.py --debug convert --source-cni kubenet --input-dir ./assessment/policies --output-dir ./converted-policies --validate --no-apply

    echo -e "${GREEN}Migration tool execution completed.${NC}"
    wait_for_user
}

# Apply Cilium NetworkPolicy
apply_cilium_policy() {
    print_section "Applying Cilium NetworkPolicy"
    echo -e "${YELLOW}Applying Cilium L7 NetworkPolicy...${NC}"

    # First remove the Kubernetes NetworkPolicy
    kubectl delete -f k8s_l3_l4_policy.yaml

    # Apply the Cilium L7 policy
    kubectl apply -f sw_l3_l4_l7_policy.yaml

    echo -e "${GREEN}Cilium NetworkPolicy applied.${NC}"
    echo -e "${YELLOW}Waiting for policy to take effect...${NC}"
    sleep 5

    wait_for_user
}

# Test connectivity with Cilium NetworkPolicy
test_connectivity_cilium_policy() {
    print_section "Testing Connectivity (Cilium NetworkPolicy)"
    echo -e "${YELLOW}Testing connectivity with Cilium NetworkPolicy...${NC}"

    # Test tiefighter to deathstar connectivity
    echo -e "\n${BOLD}Testing tiefighter to deathstar connectivity:${NC}"
    kubectl exec tiefighter -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing > /dev/null
    print_connectivity_result "tiefighter" "deathstar (POST /v1/request-landing)" $?

    kubectl exec tiefighter -- curl -s -XPUT deathstar.default.svc.cluster.local/v1/exhaust-port > /dev/null
    print_connectivity_result "tiefighter" "deathstar (PUT /v1/exhaust-port)" $?

    # Test xwing to deathstar connectivity
    echo -e "\n${BOLD}Testing xwing to deathstar connectivity:${NC}"
    kubectl exec xwing -- curl -s -XPOST deathstar.default.svc.cluster.local/v1/request-landing > /dev/null
    print_connectivity_result "xwing" "deathstar (POST /v1/request-landing)" $?

    echo -e "\n${BOLD}Summary:${NC}"
    echo -e "  Cilium NetworkPolicy allows POST /v1/request-landing from tiefighter to deathstar"
    echo -e "  Cilium NetworkPolicy blocks PUT /v1/exhaust-port from tiefighter to deathstar"
    echo -e "  Cilium NetworkPolicy blocks all traffic from xwing to deathstar"
    echo -e "  Cilium NetworkPolicy can filter based on HTTP methods and paths"

    wait_for_user
}

# Clean up resources
cleanup() {
    if [ "$SKIP_CLEANUP" = false ]; then
        print_section "Cleaning Up Resources"
        echo -e "${YELLOW}Cleaning up resources...${NC}"

        # Delete the Star Wars demo application
        kubectl delete -f http-sw-app.yaml --ignore-not-found

        # Delete the network policies
        kubectl delete -f k8s_l3_l4_policy.yaml --ignore-not-found
        kubectl delete -f sw_l3_l4_l7_policy.yaml --ignore-not-found

        # Delete the assessment and converted policies directories
        rm -rf assessment converted-policies

        echo -e "${GREEN}Cleanup completed.${NC}"
    else
        echo -e "${YELLOW}Skipping cleanup as requested.${NC}"
    fi
}

# Main function
main() {
    print_section "Starting Star Wars Migration Demo"
    echo -e "${YELLOW}This demo will show the migration from Kubernetes NetworkPolicies to Cilium NetworkPolicies${NC}"

    # Register cleanup function to run on script exit
    trap cleanup EXIT

    # Change to the script directory
    cd "$(dirname "$0")"

    check_minikube
    check_cilium
    deploy_demo_app
    test_connectivity_no_policy
    apply_k8s_policy
    test_connectivity_k8s_policy
    run_migration_tool
    apply_cilium_policy
    test_connectivity_cilium_policy

    print_section "Demo Completed"
    echo -e "${GREEN}Star Wars Migration Demo completed successfully!${NC}"
    echo -e "\n${BOLD}What we demonstrated:${NC}"
    echo -e "1. Connectivity without any network policies"
    echo -e "2. Connectivity with Kubernetes NetworkPolicies (L3/L4)"
    echo -e "3. Migration from Kubernetes NetworkPolicies to Cilium NetworkPolicies"
    echo -e "4. Connectivity with Cilium NetworkPolicies (L3/L4/L7)"
    echo -e "\n${BOLD}Key takeaways:${NC}"
    echo -e "- Kubernetes NetworkPolicies can only filter based on IP and port (L3/L4)"
    echo -e "- Cilium NetworkPolicies can filter based on HTTP methods and paths (L7)"
    echo -e "- Our migration tool can convert Kubernetes NetworkPolicies to Cilium NetworkPolicies"
    echo -e "- Cilium provides more fine-grained control over network traffic"
}

# Parse command line arguments
parse_args "$@"

# Run the main function
main
