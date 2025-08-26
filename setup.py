#!/usr/bin/env python3
"""
Setup script for Bug Bounty Automation Tool
Created by r0tbin
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = requirements_file.read_text(encoding="utf-8").strip().split("\n")
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith("#")]

setup(
    name="bugbounty-tool",
    version="1.0.0",
    author="r0tbin",
    author_email="",
    description="A personal terminal-based bug bounty automation tool with Telegram integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/r0tbin/bugbounty-tool",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: System :: Systems Administration",
        "Environment :: Console",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "r0tbb=bugbounty.cli:main",
            "bb=bugbounty.cli:main",
            "bugbounty=bugbounty.cli:main",
            "bugbounty-bot=bugbounty.telegram_bot:main",
        ],
    },
    include_package_data=True,
    package_data={
        "bugbounty": [],
    },
    data_files=[
        ("templates", ["templates/tasks.sample.yaml", "templates/juicy_filters.yaml"]),
        ("scripts", ["scripts/postinstall.sh"]),
    ],
    zip_safe=False,
    keywords="bugbounty security automation recon hacking pentesting telegram",
    project_urls={
        "Bug Reports": "https://github.com/r0tbin/bugbounty-tool/issues",
        "Source": "https://github.com/r0tbin/bugbounty-tool",
        "Documentation": "https://github.com/r0tbin/bugbounty-tool/blob/main/README.md",
    },
)