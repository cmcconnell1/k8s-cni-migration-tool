#!/bin/bash
# Network Policy tests for CNI Migration Tool

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

# Test default deny policy
test_default_deny() {
    print_header "Testing Default Deny Policy"
    
    # Get pod IPs
    POD_A_IP=$(kubectl get pod pod-a -n test-pods -o jsonpath='{.status.podIP}')
    POD_B_IP=$(kubectl get pod pod-b -n test-pods -o jsonpath='{.status.podIP}')
    
    print_info "Pod A IP: ${POD_A_IP}"
    print_info "Pod B IP: ${POD_B_IP}"
    
    # Apply default deny policy
    print_info "Applying default deny policy..."
    kubectl apply -f ../test-apps/network-policies/k8s/default-deny.yaml
    
    # Wait for policy to take effect
    print_info "Waiting for policy to take effect..."
    sleep 5
    
    # Test connectivity from pod-a to pod-b (should fail)
    print_info "Testing connectivity from pod-a to pod-b (should fail)..."
    if ! kubectl exec -n test-pods pod-a -- wget -q -O- --timeout=5 http://${POD_B_IP} > /dev/null 2>&1; then
        print_success "pod-a cannot reach pod-b (expected)"
    else
        print_error "pod-a can reach pod-b (unexpected)"
        return 1
    fi
    
    # Test connectivity from pod-b to pod-a (should fail)
    print_info "Testing connectivity from pod-b to pod-a (should fail)..."
    if ! kubectl exec -n test-pods pod-b -- wget -q -O- --timeout=5 http://${POD_A_IP} > /dev/null 2>&1; then
        print_success "pod-b cannot reach pod-a (expected)"
    else
        print_error "pod-b can reach pod-a (unexpected)"
        return 1
    fi
    
    # Clean up
    print_info "Cleaning up default deny policy..."
    kubectl delete -f ../test-apps/network-policies/k8s/default-deny.yaml
    
    # Wait for policy to be removed
    print_info "Waiting for policy to be removed..."
    sleep 5
    
    return 0
}

# Test allow pod-a to pod-b policy
test_allow_pod_a_to_pod_b() {
    print_header "Testing Allow Pod-A to Pod-B Policy"
    
    # Get pod IPs
    POD_A_IP=$(kubectl get pod pod-a -n test-pods -o jsonpath='{.status.podIP}')
    POD_B_IP=$(kubectl get pod pod-b -n test-pods -o jsonpath='{.status.podIP}')
    
    print_info "Pod A IP: ${POD_A_IP}"
    print_info "Pod B IP: ${POD_B_IP}"
    
    # Apply default deny policy
    print_info "Applying default deny policy..."
    kubectl apply -f ../test-apps/network-policies/k8s/default-deny.yaml
    
    # Apply allow pod-a to pod-b policy
    print_info "Applying allow pod-a to pod-b policy..."
    kubectl apply -f ../test-apps/network-policies/k8s/allow-pod-a-to-pod-b.yaml
    
    # Apply allow DNS policy
    print_info "Applying allow DNS policy..."
    kubectl apply -f ../test-apps/network-policies/k8s/allow-dns.yaml
    
    # Wait for policies to take effect
    print_info "Waiting for policies to take effect..."
    sleep 5
    
    # Test connectivity from pod-a to pod-b (should succeed)
    print_info "Testing connectivity from pod-a to pod-b (should succeed)..."
    if kubectl exec -n test-pods pod-a -- wget -q -O- --timeout=5 http://${POD_B_IP} > /dev/null; then
        print_success "pod-a can reach pod-b (expected)"
    else
        print_error "pod-a cannot reach pod-b (unexpected)"
        return 1
    fi
    
    # Test connectivity from pod-b to pod-a (should fail)
    print_info "Testing connectivity from pod-b to pod-a (should fail)..."
    if ! kubectl exec -n test-pods pod-b -- wget -q -O- --timeout=5 http://${POD_A_IP} > /dev/null 2>&1; then
        print_success "pod-b cannot reach pod-a (expected)"
    else
        print_error "pod-b can reach pod-a (unexpected)"
        return 1
    fi
    
    # Clean up
    print_info "Cleaning up policies..."
    kubectl delete -f ../test-apps/network-policies/k8s/allow-pod-a-to-pod-b.yaml
    kubectl delete -f ../test-apps/network-policies/k8s/allow-dns.yaml
    kubectl delete -f ../test-apps/network-policies/k8s/default-deny.yaml
    
    # Wait for policies to be removed
    print_info "Waiting for policies to be removed..."
    sleep 5
    
    return 0
}

# Test DNS policy
test_dns_policy() {
    print_header "Testing DNS Policy"
    
    # Apply default deny policy
    print_info "Applying default deny policy..."
    kubectl apply -f ../test-apps/network-policies/k8s/default-deny.yaml
    
    # Wait for policy to take effect
    print_info "Waiting for policy to take effect..."
    sleep 5
    
    # Test DNS resolution (should fail)
    print_info "Testing DNS resolution without DNS policy (should fail)..."
    if ! kubectl exec -n test-pods pod-a -- nslookup kubernetes.default.svc.cluster.local > /dev/null 2>&1; then
        print_success "DNS resolution failed (expected)"
    else
        print_error "DNS resolution succeeded (unexpected)"
        return 1
    fi
    
    # Apply allow DNS policy
    print_info "Applying allow DNS policy..."
    kubectl apply -f ../test-apps/network-policies/k8s/allow-dns.yaml
    
    # Wait for policy to take effect
    print_info "Waiting for policy to take effect..."
    sleep 5
    
    # Test DNS resolution (should succeed)
    print_info "Testing DNS resolution with DNS policy (should succeed)..."
    if kubectl exec -n test-pods pod-a -- nslookup kubernetes.default.svc.cluster.local > /dev/null; then
        print_success "DNS resolution succeeded (expected)"
    else
        print_error "DNS resolution failed (unexpected)"
        return 1
    fi
    
    # Clean up
    print_info "Cleaning up policies..."
    kubectl delete -f ../test-apps/network-policies/k8s/allow-dns.yaml
    kubectl delete -f ../test-apps/network-policies/k8s/default-deny.yaml
    
    # Wait for policies to be removed
    print_info "Waiting for policies to be removed..."
    sleep 5
    
    return 0
}

# Main function
main() {
    print_header "Running Network Policy Tests"
    
    # Check if test pods exist
    if ! kubectl get pod pod-a -n test-pods &> /dev/null || ! kubectl get pod pod-b -n test-pods &> /dev/null; then
        print_error "Test pods not found. Please deploy test pods first."
        exit 1
    fi
    
    # Run tests
    FAILED=0
    
    test_default_deny || FAILED=$((FAILED+1))
    test_allow_pod_a_to_pod_b || FAILED=$((FAILED+1))
    test_dns_policy || FAILED=$((FAILED+1))
    
    # Print summary
    print_header "Network Policy Test Summary"
    
    if [ $FAILED -eq 0 ]; then
        print_success "All network policy tests passed!"
    else
        print_error "${FAILED} network policy tests failed."
        exit 1
    fi
}

# Run main function
main
