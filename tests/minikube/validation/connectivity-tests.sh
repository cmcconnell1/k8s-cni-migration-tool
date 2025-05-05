#!/bin/bash
# Connectivity tests for CNI Migration Tool

set -e

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

# Test pod-to-pod connectivity
test_pod_to_pod() {
    print_header "Testing Pod-to-Pod Connectivity"
    
    # Get pod IPs
    POD_A_IP=$(kubectl get pod pod-a -n test-pods -o jsonpath='{.status.podIP}')
    POD_B_IP=$(kubectl get pod pod-b -n test-pods -o jsonpath='{.status.podIP}')
    
    print_info "Pod A IP: ${POD_A_IP}"
    print_info "Pod B IP: ${POD_B_IP}"
    
    # Test connectivity from pod-a to pod-b
    print_info "Testing connectivity from pod-a to pod-b..."
    if kubectl exec -n test-pods pod-a -- wget -q -O- --timeout=5 http://${POD_B_IP} > /dev/null; then
        print_success "pod-a can reach pod-b"
    else
        print_error "pod-a cannot reach pod-b"
        return 1
    fi
    
    # Test connectivity from pod-b to pod-a
    print_info "Testing connectivity from pod-b to pod-a..."
    if kubectl exec -n test-pods pod-b -- wget -q -O- --timeout=5 http://${POD_A_IP} > /dev/null; then
        print_success "pod-b can reach pod-a"
    else
        print_error "pod-b cannot reach pod-a"
        return 1
    fi
    
    return 0
}

# Test pod-to-service connectivity
test_pod_to_service() {
    print_header "Testing Pod-to-Service Connectivity"
    
    # Create services for pods
    print_info "Creating services for pods..."
    kubectl create service clusterip pod-a-svc --tcp=80:80 -n test-pods --dry-run=client -o yaml | \
        kubectl label --local -f - app=pod-a -o yaml | \
        kubectl create -f -
    
    kubectl create service clusterip pod-b-svc --tcp=80:80 -n test-pods --dry-run=client -o yaml | \
        kubectl label --local -f - app=pod-b -o yaml | \
        kubectl create -f -
    
    # Wait for endpoints to be ready
    print_info "Waiting for endpoints to be ready..."
    kubectl wait --for=condition=ready pod -l app=pod-a -n test-pods --timeout=60s
    kubectl wait --for=condition=ready pod -l app=pod-b -n test-pods --timeout=60s
    
    # Get service IPs
    POD_A_SVC=$(kubectl get service pod-a-svc -n test-pods -o jsonpath='{.spec.clusterIP}')
    POD_B_SVC=$(kubectl get service pod-b-svc -n test-pods -o jsonpath='{.spec.clusterIP}')
    
    print_info "Pod A Service IP: ${POD_A_SVC}"
    print_info "Pod B Service IP: ${POD_B_SVC}"
    
    # Test connectivity from pod-a to pod-b service
    print_info "Testing connectivity from pod-a to pod-b service..."
    if kubectl exec -n test-pods pod-a -- wget -q -O- --timeout=5 http://${POD_B_SVC} > /dev/null; then
        print_success "pod-a can reach pod-b service"
    else
        print_error "pod-a cannot reach pod-b service"
        return 1
    fi
    
    # Test connectivity from pod-b to pod-a service
    print_info "Testing connectivity from pod-b to pod-a service..."
    if kubectl exec -n test-pods pod-b -- wget -q -O- --timeout=5 http://${POD_A_SVC} > /dev/null; then
        print_success "pod-b can reach pod-a service"
    else
        print_error "pod-b cannot reach pod-a service"
        return 1
    fi
    
    # Clean up services
    print_info "Cleaning up services..."
    kubectl delete service pod-a-svc pod-b-svc -n test-pods
    
    return 0
}

# Test DNS resolution
test_dns_resolution() {
    print_header "Testing DNS Resolution"
    
    # Test DNS resolution from pod-a
    print_info "Testing DNS resolution from pod-a..."
    if kubectl exec -n test-pods pod-a -- nslookup kubernetes.default.svc.cluster.local > /dev/null; then
        print_success "pod-a can resolve DNS"
    else
        print_error "pod-a cannot resolve DNS"
        return 1
    fi
    
    # Test DNS resolution from pod-b
    print_info "Testing DNS resolution from pod-b..."
    if kubectl exec -n test-pods pod-b -- nslookup kubernetes.default.svc.cluster.local > /dev/null; then
        print_success "pod-b can resolve DNS"
    else
        print_error "pod-b cannot resolve DNS"
        return 1
    fi
    
    return 0
}

# Test external connectivity
test_external_connectivity() {
    print_header "Testing External Connectivity"
    
    # Test external connectivity from pod-a
    print_info "Testing external connectivity from pod-a..."
    if kubectl exec -n test-pods pod-a -- wget -q -O- --timeout=5 https://www.google.com > /dev/null; then
        print_success "pod-a can reach external sites"
    else
        print_error "pod-a cannot reach external sites"
        return 1
    fi
    
    # Test external connectivity from pod-b
    print_info "Testing external connectivity from pod-b..."
    if kubectl exec -n test-pods pod-b -- wget -q -O- --timeout=5 https://www.google.com > /dev/null; then
        print_success "pod-b can reach external sites"
    else
        print_error "pod-b cannot reach external sites"
        return 1
    fi
    
    return 0
}

# Main function
main() {
    print_header "Running Connectivity Tests"
    
    # Check if test pods exist
    if ! kubectl get pod pod-a -n test-pods &> /dev/null || ! kubectl get pod pod-b -n test-pods &> /dev/null; then
        print_error "Test pods not found. Please deploy test pods first."
        exit 1
    fi
    
    # Run tests
    FAILED=0
    
    test_pod_to_pod || FAILED=$((FAILED+1))
    test_pod_to_service || FAILED=$((FAILED+1))
    test_dns_resolution || FAILED=$((FAILED+1))
    test_external_connectivity || FAILED=$((FAILED+1))
    
    # Print summary
    print_header "Connectivity Test Summary"
    
    if [ $FAILED -eq 0 ]; then
        print_success "All connectivity tests passed!"
    else
        print_error "${FAILED} connectivity tests failed."
        exit 1
    fi
}

# Run main function
main
