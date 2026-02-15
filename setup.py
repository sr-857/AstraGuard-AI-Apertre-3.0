#!/usr/bin/env python3
"""
AstraGuard AI Setup Configuration
Security-First Autonomous Defense System for CubeSats
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("src/config/requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="astraguard-ai",
    version="1.0.0",
    author="Subhajit Roy",
    author_email="sr-857@github.com",
    description="Security-First AI System for Threat Detection and Autonomous Defense",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sr-857/AstraGuard",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "astraguard=cli:main",
        ],
    },
    include_package_data=True,
    keywords="ai security cubesat anomaly-detection pathway bdh hackathon",
    project_urls={
        "Bug Reports": "https://github.com/sr-857/AstraGuard/issues",
        "Source": "https://github.com/sr-857/AstraGuard",
        "Hackathon": "https://pathway.com/",
    },
)

#setup.py ends here