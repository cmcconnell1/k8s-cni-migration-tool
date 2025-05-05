.PHONY: install test clean run-assessment run-convert run-plan run-validate run-workflow help

# Default target
all: install

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	mkdir -p tests/test_output
	cd tests && bash test_tool.sh

# Clean up
clean:
	rm -rf assessment converted-policies migration-plan.md validation-reports
	rm -rf tests/test_output

# Run assessment
run-assessment:
	python cni_migration.py assess --output-dir ./assessment

# Run policy conversion
run-convert:
	python cni_migration.py convert --source-cni calico --input-dir ./assessment/policies --output-dir ./converted-policies --validate --no-apply

# Run migration planning
run-plan:
	python cni_migration.py plan --target-cidr 10.245.0.0/16 --approach hybrid --output-file ./migration-plan.md

# Run validation
run-validate-pre:
	python cni_migration.py validate --phase pre --report-dir ./validation-reports

run-validate-during:
	python cni_migration.py validate --phase during --source-cni calico --target-cidr 10.245.0.0/16 --report-dir ./validation-reports

run-validate-post:
	python cni_migration.py validate --phase post --source-cni calico --report-dir ./validation-reports

# Run full workflow
run-workflow:
	bash examples/migration_workflow.sh

# Help
help:
	@echo "Available targets:"
	@echo "  install            - Install dependencies"
	@echo "  test               - Run tests"
	@echo "  clean              - Clean up generated files"
	@echo "  run-assessment     - Run CNI assessment"
	@echo "  run-convert        - Convert network policies"
	@echo "  run-plan           - Generate migration plan"
	@echo "  run-validate-pre   - Validate pre-migration connectivity"
	@echo "  run-validate-during- Validate connectivity during migration"
	@echo "  run-validate-post  - Validate post-migration connectivity"
	@echo "  run-workflow       - Run the complete migration workflow"
