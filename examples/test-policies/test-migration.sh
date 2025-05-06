#!/bin/bash

# Interactive test script for validating CNI migration with test policies
# This script applies test policies to a minikube cluster, runs the migration tool,
# and validates that the converted policies work as expected.
# It demonstrates connectivity changes before and after applying policies.

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Global variables
INTERACTIVE=true
RESULTS_FILE="test-results.txt"

# Function to print colored output
print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
    if [ -n "$RESULTS_FILE" ]; then
        echo "[INFO] $1" >> "$RESULTS_FILE"
    fi
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    if [ -n "$RESULTS_FILE" ]; then
        echo "[SUCCESS] $1" >> "$RESULTS_FILE"
    fi
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    if [ -n "$RESULTS_FILE" ]; then
        echo "[ERROR] $1" >> "$RESULTS_FILE"
    fi
}

print_step() {
    echo -e "\n${BLUE}${BOLD}=== $1 ===${NC}\n"
    if [ -n "$RESULTS_FILE" ]; then
        echo -e "\n=== $1 ===\n" >> "$RESULTS_FILE"
    fi
}

print_connectivity_result() {
    local from=$1
    local to=$2
    local namespace=${3:-default}
    local result=$4

    if [ "$result" -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} $from → $to${namespace:+.$namespace}: ${GREEN}Connected${NC}"
        if [ -n "$RESULTS_FILE" ]; then
            echo "  ✓ $from → $to${namespace:+.$namespace}: Connected" >> "$RESULTS_FILE"
        fi
    else
        echo -e "  ${RED}✗${NC} $from → $to${namespace:+.$namespace}: ${RED}Blocked${NC}"
        if [ -n "$RESULTS_FILE" ]; then
            echo "  ✗ $from → $to${namespace:+.$namespace}: Blocked" >> "$RESULTS_FILE"
        fi
    fi
}

# Function to wait for user input in interactive mode
wait_for_user() {
    if [ "$INTERACTIVE" = true ]; then
        echo -e "\n${CYAN}Press Enter to continue...${NC}"
        read -r
    fi
}

# Check if minikube is running
check_minikube() {
    print_info "Checking if minikube is running..."
    if ! minikube status | grep -q "Running"; then
        print_error "Minikube is not running. Please start minikube first."
        exit 1
    fi
    print_success "Minikube is running."
}

# Create test namespaces
create_namespaces() {
    print_step "Creating Test Namespaces"
    print_info "Creating test namespaces..."
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    kubectl label namespace monitoring purpose=monitoring --overwrite

    kubectl create namespace production --dry-run=client -o yaml | kubectl apply -f -
    kubectl label namespace production environment=production --overwrite

    print_success "Test namespaces created."
    wait_for_user
}

# Create test pods
create_test_pods() {
    print_step "Creating Test Pods"
    print_info "Creating test pods for connectivity testing..."

    # Frontend pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: frontend
  namespace: default
  labels:
    app: frontend
spec:
  containers:
  - name: nginx
    image: nginx:alpine
    ports:
    - containerPort: 80
EOF

    # Backend pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: backend
  namespace: default
  labels:
    app: backend
spec:
  containers:
  - name: nginx
    image: nginx:alpine
    ports:
    - containerPort: 8080
EOF

    # Web pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: web
  namespace: default
  labels:
    app: web
spec:
  containers:
  - name: nginx
    image: nginx:alpine
    ports:
    - containerPort: 9090
EOF

    # API pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: api
  namespace: default
  labels:
    app: api
spec:
  containers:
  - name: nginx
    image: nginx:alpine
    ports:
    - containerPort: 443
EOF

    # Database pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: database
  namespace: default
  labels:
    app: database
spec:
  containers:
  - name: mysql
    image: mysql:5.7
    env:
    - name: MYSQL_ROOT_PASSWORD
      value: password
    ports:
    - containerPort: 3306
EOF

    # Cache pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cache
  namespace: default
  labels:
    app: cache
spec:
  containers:
  - name: redis
    image: redis:alpine
    ports:
    - containerPort: 6379
EOF

    # Production frontend pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: prod-frontend
  namespace: production
  labels:
    role: frontend
spec:
  containers:
  - name: nginx
    image: nginx:alpine
    ports:
    - containerPort: 80
EOF

    # Monitoring pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: prometheus
  namespace: monitoring
  labels:
    app: prometheus
spec:
  containers:
  - name: prometheus
    image: prom/prometheus:latest
    ports:
    - containerPort: 9090
EOF

    print_success "Test pods created."

    # Wait for pods to be ready
    print_info "Waiting for pods to be ready..."
    kubectl wait --for=condition=ready pod --all --timeout=120s
    kubectl wait --for=condition=ready pod --all -n production --timeout=60s
    kubectl wait --for=condition=ready pod --all -n monitoring --timeout=60s

    print_success "All pods are ready."
    wait_for_user
}

# Test connectivity between pods
test_connectivity() {
    local phase=$1
    print_step "Testing Connectivity - $phase"
    print_info "Testing pod-to-pod connectivity..."

    echo -e "\n${BOLD}Testing basic connectivity:${NC}"

    # Test frontend to backend connectivity (should be blocked with policies)
    kubectl exec frontend -- wget -q -T 2 -O /dev/null http://backend:8080 > /dev/null 2>&1
    print_connectivity_result "frontend" "backend" "default" $?

    # Test frontend to web connectivity (should be blocked with policies)
    kubectl exec frontend -- wget -q -T 2 -O /dev/null http://web:9090 > /dev/null 2>&1
    print_connectivity_result "frontend" "web" "default" $?

    # Test monitoring namespace to web connectivity (should be allowed with policies)
    kubectl exec -n monitoring prometheus -- wget -q -T 2 -O /dev/null http://web.default.svc.cluster.local:9090 > /dev/null 2>&1
    print_connectivity_result "prometheus" "web" "monitoring→default" $?

    # Test production frontend to cache connectivity (should be allowed with policies)
    kubectl exec -n production prod-frontend -- wget -q -T 2 -O /dev/null http://cache.default.svc.cluster.local:6379 > /dev/null 2>&1
    print_connectivity_result "prod-frontend" "cache" "production→default" $?

    echo -e "\n${BOLD}Summary:${NC}"
    if [ "$phase" == "Before Policies" ]; then
        echo -e "  All connections should be ${GREEN}allowed${NC} before applying network policies."
    elif [ "$phase" == "After Default Policies" ]; then
        echo -e "  Some connections should be ${RED}blocked${NC} based on the applied network policies."
        echo -e "  - frontend → backend: ${RED}blocked${NC} (policy allows only from frontend to backend port 8080)"
        echo -e "  - frontend → web: ${RED}blocked${NC} (policy allows only from monitoring namespace)"
        echo -e "  - prometheus → web: ${GREEN}allowed${NC} (policy allows from monitoring namespace)"
        echo -e "  - prod-frontend → cache: ${GREEN}allowed${NC} (policy allows from production namespace with role=frontend)"
    elif [ "$phase" == "After Cilium Policies" ]; then
        echo -e "  Connectivity should be the ${YELLOW}same as with default policies${NC} if conversion was successful."
    fi

    wait_for_user
}

# Apply test policies
apply_test_policies() {
    print_step "Applying Network Policies"
    print_info "Applying test network policies..."

    # Apply all policies in the test-policies directory
    kubectl apply -f $(dirname "$0")/*.yaml

    print_success "Test network policies applied."
    print_info "Waiting for policies to take effect..."
    sleep 5

    wait_for_user
}

# Run the migration tool
run_migration_tool() {
    print_step "Running CNI Migration Tool"
    print_info "Running the CNI migration tool..."

    # Navigate to the parent directory
    cd $(dirname "$0")/../..

    # Activate virtual environment if it exists
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi

    # Run the assessment
    print_info "Running assessment..."
    python cni_migration.py --debug assess --output-dir ./test-assessment

    # Convert policies
    print_info "Converting policies..."
    python cni_migration.py --debug convert --source-cni calico --input-dir ./test-assessment/policies --output-dir ./test-converted-policies --validate --no-apply

    # Generate migration plan
    print_info "Generating migration plan..."
    python cni_migration.py --debug plan --target-cidr 10.245.0.0/16 --approach hybrid --output-file ./test-migration-plan.md

    print_success "Migration tool execution completed."
    wait_for_user
}

# Validate the converted policies
validate_policies() {
    print_step "Validating Converted Policies"
    print_info "Validating converted policies..."

    # Check if the converted policies directory exists
    if [ ! -d "./test-converted-policies" ]; then
        print_error "Converted policies directory not found."
        exit 1
    fi

    # Count the number of original and converted policies
    original_count=$(find $(dirname "$0") -name "*.yaml" | wc -l)
    converted_count=$(find ./test-converted-policies -name "*.yaml" | wc -l)

    print_info "Original policies: $original_count"
    print_info "Converted policies: $converted_count"

    if [ "$converted_count" -lt "$original_count" ]; then
        print_error "Not all policies were converted."
        exit 1
    fi

    print_success "All policies were converted successfully."

    # Display the converted policies
    if [ "$INTERACTIVE" = true ]; then
        echo -e "\n${BOLD}Sample of converted policies:${NC}"
        find ./test-converted-policies -name "*.yaml" | head -n 2 | while read -r policy; do
            echo -e "\n${CYAN}$policy:${NC}"
            cat "$policy" | grep -v "^#" | grep -v "^$" | head -n 15
            echo -e "${CYAN}[...truncated...]${NC}"
        done
    fi

    # Apply the converted policies if Cilium is installed
    if kubectl get pods -n kube-system | grep -q "cilium"; then
        print_info "Cilium detected. Applying converted policies..."

        # First remove the original policies
        kubectl delete -f $(dirname "$0")/*.yaml --ignore-not-found

        # Apply the converted policies
        kubectl apply -f ./test-converted-policies/k8s/

        print_success "Converted policies applied."
        print_info "Waiting for policies to take effect..."
        sleep 5
    else
        print_info "Cilium not detected. Skipping application of converted policies."
        print_info "To test with Cilium policies, install Cilium and run this script again."
    fi

    wait_for_user
}

# Clean up resources
cleanup() {
    if [ "$1" != "--no-cleanup" ]; then
        print_step "Cleaning Up Resources"
        print_info "Cleaning up resources..."

        # Delete test pods
        kubectl delete pod frontend backend web api database cache --ignore-not-found

        # Delete test pods in other namespaces
        kubectl delete pod -n production prod-frontend --ignore-not-found
        kubectl delete pod -n monitoring prometheus --ignore-not-found

        # Delete network policies
        kubectl delete -f $(dirname "$0")/*.yaml --ignore-not-found
        kubectl delete -f ./test-converted-policies/k8s/ --ignore-not-found 2>/dev/null

        # Delete namespaces
        kubectl delete namespace monitoring production --ignore-not-found

        # Delete migration tool output
        if [ -n "$RESULTS_FILE" ] && [ -f "$RESULTS_FILE" ]; then
            print_info "Test results saved to $RESULTS_FILE"
        else
            rm -rf ./test-assessment ./test-converted-policies ./test-migration-plan.md
        fi

        print_success "Cleanup completed."
    else
        print_info "Skipping cleanup as requested."
        if [ -n "$RESULTS_FILE" ] && [ -f "$RESULTS_FILE" ]; then
            print_info "Test results saved to $RESULTS_FILE"
        fi
    fi
}

# Parse command line arguments
parse_args() {
    for arg in "$@"; do
        case $arg in
            --no-interactive)
                INTERACTIVE=false
                shift
                ;;
            --no-cleanup)
                cleanup_flag="--no-cleanup"
                shift
                ;;
            --results-file=*)
                RESULTS_FILE="${arg#*=}"
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --no-interactive     Run without interactive prompts"
                echo "  --no-cleanup         Don't clean up resources after running"
                echo "  --results-file=FILE  Save test results to specified file"
                echo "  --help               Show this help message"
                exit 0
                ;;
        esac
    done
}

# Main execution
main() {
    print_step "Starting CNI Migration Test"
    print_info "Starting CNI migration test with test policies..."

    # Initialize results file if specified
    if [ -n "$RESULTS_FILE" ]; then
        echo "# CNI Migration Test Results - $(date)" > "$RESULTS_FILE"
        echo "" >> "$RESULTS_FILE"
    fi

    # Register cleanup function to run on script exit
    trap "cleanup $cleanup_flag" EXIT

    check_minikube
    create_namespaces
    create_test_pods

    # Test connectivity before applying policies
    test_connectivity "Before Policies"

    # Apply and test with default policies
    apply_test_policies
    test_connectivity "After Default Policies"

    # Run the migration tool
    run_migration_tool
    validate_policies

    # Test with Cilium policies if available
    if kubectl get pods -n kube-system | grep -q "cilium"; then
        test_connectivity "After Cilium Policies"
    fi

    print_step "Test Completed"
    print_success "CNI migration test completed successfully!"

    if [ -n "$RESULTS_FILE" ]; then
        print_info "Test results saved to $RESULTS_FILE"
    fi
}

# Parse arguments and run the main function
parse_args "$@"
main
