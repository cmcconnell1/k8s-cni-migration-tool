#!/bin/bash
# Setup script for Minikube with Weave CNI

set -e

# Configuration
MINIKUBE_MEMORY=${MINIKUBE_MEMORY:-"4096"}
MINIKUBE_CPUS=${MINIKUBE_CPUS:-"2"}
MINIKUBE_DISK_SIZE=${MINIKUBE_DISK_SIZE:-"20g"}
KUBERNETES_VERSION=${KUBERNETES_VERSION:-"v1.26.3"}

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

# Check prerequisites
check_prerequisites() {
    print_header "Checking prerequisites"
    
    # Check if minikube is installed
    if ! command -v minikube &> /dev/null; then
        print_error "minikube is not installed. Please install minikube first."
        exit 1
    fi
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi
    
    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        print_error "jq is not installed. Please install jq first."
        exit 1
    fi
    
    print_info "All prerequisites are met."
}

# Start minikube with CNI none
start_minikube() {
    print_header "Starting Minikube"
    
    # Check if minikube is already running
    if minikube status | grep -q "Running"; then
        print_info "Minikube is already running. Stopping it first..."
        minikube stop
        minikube delete
    fi
    
    # Start minikube with CNI none
    print_info "Starting Minikube with CNI none..."
    minikube start \
        --kubernetes-version=${KUBERNETES_VERSION} \
        --memory=${MINIKUBE_MEMORY} \
        --cpus=${MINIKUBE_CPUS} \
        --disk-size=${MINIKUBE_DISK_SIZE} \
        --network-plugin=cni \
        --cni=false
    
    print_info "Minikube started successfully."
}

# Install Weave CNI
install_weave() {
    print_header "Installing Weave CNI"
    
    # Apply Weave manifest
    print_info "Applying Weave manifest..."
    kubectl apply -f "https://github.com/weaveworks/weave/releases/download/v2.8.1/weave-daemonset-k8s.yaml"
    
    # Wait for Weave to be ready
    print_info "Waiting for Weave to be ready..."
    kubectl wait --for=condition=ready pod -l name=weave-net -n kube-system --timeout=300s
    
    print_info "Weave installed successfully."
}

# Verify Weave installation
verify_weave() {
    print_header "Verifying Weave installation"
    
    # Check Weave pods
    print_info "Checking Weave pods..."
    kubectl get pods -n kube-system -l name=weave-net
    
    # Check node status
    print_info "Checking node status..."
    kubectl get nodes -o wide
    
    # Check CNI configuration
    print_info "Checking CNI configuration..."
    minikube ssh "ls -la /etc/cni/net.d/"
    
    print_info "Weave verification completed."
}

# Deploy test pods
deploy_test_pods() {
    print_header "Deploying test pods"
    
    # Create test namespace
    kubectl create namespace test-pods || true
    
    # Deploy test pods
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pod-a
  namespace: test-pods
  labels:
    app: pod-a
spec:
  containers:
  - name: nginx
    image: nginx:alpine
---
apiVersion: v1
kind: Pod
metadata:
  name: pod-b
  namespace: test-pods
  labels:
    app: pod-b
spec:
  containers:
  - name: nginx
    image: nginx:alpine
EOF
    
    # Wait for pods to be ready
    print_info "Waiting for test pods to be ready..."
    kubectl wait --for=condition=ready pod -l app=pod-a -n test-pods --timeout=120s
    kubectl wait --for=condition=ready pod -l app=pod-b -n test-pods --timeout=120s
    
    print_info "Test pods deployed successfully."
}

# Test connectivity
test_connectivity() {
    print_header "Testing connectivity"
    
    # Get pod IPs
    POD_A_IP=$(kubectl get pod pod-a -n test-pods -o jsonpath='{.status.podIP}')
    POD_B_IP=$(kubectl get pod pod-b -n test-pods -o jsonpath='{.status.podIP}')
    
    print_info "Pod A IP: ${POD_A_IP}"
    print_info "Pod B IP: ${POD_B_IP}"
    
    # Test connectivity from pod-a to pod-b
    print_info "Testing connectivity from pod-a to pod-b..."
    kubectl exec -n test-pods pod-a -- wget -q -O- --timeout=5 http://${POD_B_IP} > /dev/null
    if [ $? -eq 0 ]; then
        print_info "Connectivity test passed: pod-a can reach pod-b."
    else
        print_error "Connectivity test failed: pod-a cannot reach pod-b."
        exit 1
    fi
    
    # Test connectivity from pod-b to pod-a
    print_info "Testing connectivity from pod-b to pod-a..."
    kubectl exec -n test-pods pod-b -- wget -q -O- --timeout=5 http://${POD_A_IP} > /dev/null
    if [ $? -eq 0 ]; then
        print_info "Connectivity test passed: pod-b can reach pod-a."
    else
        print_error "Connectivity test failed: pod-b cannot reach pod-a."
        exit 1
    fi
    
    print_info "Connectivity tests completed successfully."
}

# Main function
main() {
    check_prerequisites
    start_minikube
    install_weave
    verify_weave
    deploy_test_pods
    test_connectivity
    
    print_header "Setup completed successfully"
    print_info "Minikube with Weave CNI is now ready for testing."
    print_info "You can now run the CNI Migration Tool to migrate from Weave to Cilium."
}

# Run main function
main
