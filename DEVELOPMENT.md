# Development Guide

This guide provides instructions for setting up a development environment for the k8s-cni-migration-tool.

## Setting Up a Development Environment

### Prerequisites

- Python 3.8 or later (Python 3.12 recommended)
- pip (latest version)
- virtualenv or venv

### Creating a Virtual Environment

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Installing Dependencies

```bash
# Install all dependencies including development dependencies
pip install -e ".[dev]"

# Or install from requirements.txt
pip install -r requirements.txt
```

### Running Tests

```bash
# Run tests
make test

# Or run pytest directly
pytest
```

### Code Formatting

```bash
# Format code with black
black .

# Sort imports with isort
isort .
```

## Project Structure

- `cni_migration.py`: Main entry point for the CLI
- `lib/`: Core functionality modules
  - `assessment.py`: CNI assessment module
  - `policy_converter.py`: Network policy conversion module
  - `migration_planner.py`: Migration plan generation module
  - `validator.py`: Connectivity validation module
  - `k8s_utils.py`: Kubernetes utility functions
- `tests/`: Test suite
- `examples/`: Example workflows and scripts
- `docs/`: Documentation

## Development Workflow

1. Create a feature branch
2. Make your changes
3. Run tests to ensure everything works
4. Format your code with black and isort
5. Submit a pull request

## Troubleshooting

### PyYAML Installation Issues

If you encounter issues installing PyYAML, try using a newer version:

```bash
pip install pyyaml>=6.0.1
```

### Python Version Compatibility

This project is designed to work with Python 3.8 or later. If you encounter compatibility issues, try using Python 3.12:

```bash
# Check your Python version
python --version

# Create a virtual environment with a specific Python version
python3.12 -m venv .venv
source .venv/bin/activate
```

### Minikube CNI Detection

When testing with Minikube, the tool will detect the default CNI as "kubenet" or "kindnet". Since these CNIs only support standard Kubernetes NetworkPolicies, the tool will use "calico" as the source CNI for policy conversion.

If you want to test with a specific CNI, you can start Minikube with that CNI:

```bash
# Start Minikube with Calico
minikube start --network-plugin=cni --cni=calico

# Or with Flannel
minikube start --network-plugin=cni --cni=flannel
```
