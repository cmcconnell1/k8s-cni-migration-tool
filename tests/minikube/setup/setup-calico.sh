#!/bin/bash
# Setup script for Minikube with Calico CNI

set -e

# Configuration
MINIKUBE_MEMORY=${MINIKUBE_MEMORY:-"4096"}
MINIKUBE_CPUS=${MINIKUBE_CPUS:-"2"}
MINIKUBE_DISK_SIZE=${MINIKUBE_DISK_SIZE:-"20g"}
CALICO_VERSION=${CALICO_VERSION:-"v3.26.1"}
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
        --cni=false \
        --extra-config=kubeadm.pod-network-cidr=192.168.0.0/16
    
    print_info "Minikube started successfully."
}

# Install Calico CNI
install_calico() {
    print_header "Installing Calico CNI"
    
    # Download Calico manifest
    print_info "Downloading Calico manifest..."
    curl -L https://docs.projectcalico.org/${CALICO_VERSION}/manifests/calico.yaml -o calico.yaml
    
    # Apply Calico manifest
    print_info "Applying Calico manifest..."
    kubectl apply -f calico.yaml
    
    # Wait for Calico to be ready
    print_info "Waiting for Calico to be ready..."
    kubectl wait --for=condition=ready pod -l k8s-app=calico-node -n kube-system --timeout=300s
    
    print_info "Calico installed successfully."
}

# Verify Calico installation
verify_calico() {
    print_header "Verifying Calico installation"
    
    # Check Calico pods
    print_info "Checking Calico pods..."
    kubectl get pods -n kube-system -l k8s-app=calico-node
    
    # Check Calico node status
    print_info "Checking Calico node status..."
    kubectl get nodes -o wide
    
    # Check CNI configuration
    print_info "Checking CNI configuration..."
    minikube ssh "ls -la /etc/cni/net.d/"
    
    print_info "Calico verification completed."
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
    install_calico
    verify_calico
    deploy_test_pods
    test_connectivity
    
    print_header "Setup completed successfully"
    print_info "Minikube with Calico CNI is now ready for testing."
    print_info "You can now run the CNI Migration Tool to migrate from Calico to Cilium."
}

# Run main function
main
