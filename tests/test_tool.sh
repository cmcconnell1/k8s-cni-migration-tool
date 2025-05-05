#!/bin/bash
# Simple test script for the CNI Migration Tool
# This script tests basic functionality without requiring a real Kubernetes cluster

set -e

# Create test directories
mkdir -p test_output/assessment
mkdir -p test_output/converted-policies

echo "Testing assessment module..."
python $(dirname $0)/../cni_migration.py --debug assess --output-dir ./test_output/assessment

echo "Testing policy converter module..."
# Create a sample Kubernetes NetworkPolicy
mkdir -p test_output/assessment/policies/k8s
cat > test_output/assessment/policies/k8s/test-policy.yaml << EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: test-network-policy
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: test
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 80
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 5432
EOF

python $(dirname $0)/../cni_migration.py --debug convert --source-cni calico --input-dir ./test_output/assessment/policies --output-dir ./test_output/converted-policies

echo "Testing migration planner module..."
python $(dirname $0)/../cni_migration.py --debug plan --target-cidr 10.245.0.0/16 --approach hybrid --output-file ./test_output/migration-plan.md

echo "All tests completed successfully!"
echo "Check the test_output directory for results."
