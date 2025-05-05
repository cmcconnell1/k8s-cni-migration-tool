# Changelog

All notable changes to the CNI Migration Tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CI/CD pipeline with GitHub Actions
- Minikube testing framework
- Documentation with MkDocs
- Python package setup
- Support for kubenet and kindnet CNIs (minikube default CNIs)

### Changed
- Removed Makefile in favor of direct script execution
- Updated documentation to reflect modern Python project practices
- Improved handling of unknown or default CNIs

## [0.1.0] - 2023-07-01

### Added
- Initial release of the CNI Migration Tool
- Assessment module to detect current CNI configuration
- Policy converter module to convert network policies to Cilium format
- Migration planner module to generate migration plans
- Validator module to test connectivity and policy enforcement
- Support for Calico, Flannel, and Weave CNIs
- Support for hybrid, multus, and clean migration approaches
- Command-line interface with Click
- Example scripts for migration workflows

[Unreleased]: https://github.com/cmcconnell1/k8s-cni-migration-tool/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cmcconnell1/k8s-cni-migration-tool/releases/tag/v0.1.0
