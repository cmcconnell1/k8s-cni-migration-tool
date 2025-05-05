#!/usr/bin/env python3
"""
Setup script for CNI Migration Tool
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read().splitlines()

setup(
    name="k8s-cni-migration-tool",
    version="0.1.0",
    author="CNI Migration Tool Contributors",
    author_email="maintainers@example.com",
    description="A tool to facilitate migration from various Kubernetes CNI solutions to Cilium",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cmcconnell1/k8s-cni-migration-tool",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "cni-migration=cni_migration:cli",
        ],
    },
    include_package_data=True,
)
