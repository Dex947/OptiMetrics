"""
OptiMetrics Setup Script

For development installation:
    pip install -e .

For distribution:
    python setup.py sdist bdist_wheel
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

setup(
    name="optimetrics",
    version="1.0.0",
    author="OptiMetrics Contributors",
    author_email="",
    description="Open-source hardware metrics collection tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/OptiMetrics",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/OptiMetrics/issues",
        "Documentation": "https://github.com/yourusername/OptiMetrics#readme",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Hardware",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "psutil>=5.9.0",
        "GPUtil>=1.4.0",
        "pynvml>=11.5.0",
        "py-cpuinfo>=9.0.0",
        "PyYAML>=6.0",
        "platformdirs>=4.0.0",
    ],
    extras_require={
        "windows": ["pywin32>=306", "wmi>=1.5.1"],
        "cloud": [
            "google-api-python-client>=2.100.0",
            "google-auth-httplib2>=0.1.0",
            "google-auth-oauthlib>=1.1.0",
            "cryptography>=41.0.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "optimetrics=hardware_logger:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
