"""
PyQuant Alexander - Crypto Quant Framework
Setup script for local package installation
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the requirements.txt file
requirements_path = Path(__file__).parent / "requirements.txt"
with open(requirements_path, "r", encoding="utf-8") as f:
    requirements = [
        line.strip()
        for line in f
        if line.strip()
        and not line.startswith("#")
        and not line.startswith("//")
    ]

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="pyquant_alexander",
    version="1.0.0",
    author="Alexander",
    description="Multi-Asset Crypto Portfolio Framework (BTC, ETH, SOL, LINK) - Alpha with Low Beta",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/pyquant_alexander",  # Update with actual repo
    
    # Package discovery
    packages=find_packages(exclude=["tests", "research", "Notebooks", "Docs"]),
    
    # Dependencies
    install_requires=requirements,
    
    # Python version requirement
    python_requires=">=3.10",
    
    # Additional metadata
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
    ],
    
    # Entry points (if you want CLI commands later)
    entry_points={
        "console_scripts": [
            # Example: "pyquant-backtest=runners.run_portfolio_backtest:main",
        ],
    },
    
    # Include additional files
    include_package_data=True,
    package_data={
        "": ["*.txt", "*.md", "*.yaml", "*.json"],
    },
    
    # Development dependencies
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "ipython>=8.0.0",
            "jupyter>=1.0.0",
        ],
    },
)

