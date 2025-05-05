# Contributing

Thank you for considering contributing to the CNI Migration Tool! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Please read and follow our [Code of Conduct](https://github.com/cmcconnell1/k8s-cni-migration-tool/blob/main/CODE_OF_CONDUCT.md).

## How to Contribute

There are many ways to contribute to the CNI Migration Tool:

- Report bugs and request features by creating issues
- Fix bugs and implement features by submitting pull requests
- Improve documentation
- Share your experience using the tool
- Help answer questions in discussions and issues

## Development Environment

### Prerequisites

- Python 3.8 or later
- Minikube for testing
- kubectl
- Git

### Setting Up Development Environment

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/cmcconnell1/k8s-cni-migration-tool.git
   cd k8s-cni-migration-tool
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

### Running Tests

Run unit tests:

```bash
pytest tests/test_comprehensive.py
```

Run Minikube tests:

```bash
cd tests/minikube
./run-tests.sh --cni calico
```

### Code Style

We use the following tools to ensure code quality:

- flake8: Check for syntax errors and code style
- black: Format code
- isort: Sort imports

Format your code before submitting a pull request:

```bash
black .
isort .
flake8 .
```

## Pull Request Process

1. Create a new branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes and commit them with descriptive commit messages
3. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
4. Create a pull request from your branch to the main repository
5. Ensure that all CI checks pass
6. Wait for a maintainer to review your pull request
7. Address any feedback from the review
8. Once approved, your pull request will be merged

## Issue Reporting

When reporting issues, please include:

- A clear and descriptive title
- A detailed description of the issue
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Screenshots or logs, if applicable
- Environment information (OS, Python version, Kubernetes version, etc.)

## Feature Requests

When requesting features, please include:

- A clear and descriptive title
- A detailed description of the feature
- Why the feature would be useful
- Any relevant examples or use cases

## Documentation

We use MkDocs with the Material theme for documentation. To build the documentation locally:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

Then open http://localhost:8000 in your browser.

## Release Process

1. Update the version number in `setup.py`
2. Update the changelog
3. Create a new tag:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   ```
4. The CI/CD pipeline will automatically build and publish the package to PyPI

## License

By contributing to the CNI Migration Tool, you agree that your contributions will be licensed under the project's MIT License.
