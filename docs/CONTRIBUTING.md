# Contributing to OptiMetrics

Thank you for your interest in contributing to OptiMetrics! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

1. Check existing issues to avoid duplicates
2. Use the bug report template
3. Include:
   - OS and Python version
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant log output

### Suggesting Features

1. Check existing feature requests
2. Describe the use case
3. Explain how it benefits users
4. Consider privacy implications

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Format code: `black src/` and `ruff check src/`
6. Commit with clear messages
7. Push and create a PR

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/OptiMetrics.git
cd OptiMetrics

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
pip install pytest black ruff

# Run tests
pytest tests/ -v
```

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for public functions
- Keep functions focused and small
- Use meaningful variable names

## Adding Hardware Adapters

1. Create `src/adapters/my_adapter.py`
2. Inherit from `BaseHardwareAdapter`
3. Implement required methods:
   - `initialize()` - Setup hardware access
   - `get_hardware_info()` - Return hardware identification
   - `collect_metrics()` - Return current metrics
   - `cleanup()` - Release resources

4. Register in `src/adapters/__init__.py`
5. Add initialization in `hardware_logger.py`
6. Update documentation

### Adapter Template

```python
"""
My Hardware Adapter

Brief description of what this adapter collects.
"""

from typing import Dict, Any, Optional
from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue


class MyAdapter(BaseHardwareAdapter):
    """
    Adapter for collecting metrics from MyHardware.
    
    Collects:
        - metric1: Description
        - metric2: Description
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        # Initialize adapter-specific state
    
    def initialize(self) -> bool:
        """Initialize hardware access."""
        try:
            # Setup code here
            self._initialized = True
            return True
        except Exception as e:
            self.record_error(str(e))
            return False
    
    def get_hardware_info(self) -> Optional[HardwareInfo]:
        """Get hardware identification."""
        return HardwareInfo(
            vendor="Vendor Name",
            model="Model Name",
            identifier="unique_identifier",
            additional_info={"key": "value"}
        )
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        """Collect current metrics."""
        metrics = {}
        
        try:
            # Collect metrics here
            metrics["my_metric"] = MetricValue(
                name="my_metric",
                value=42.0,
                unit="%",
                source="my_adapter"
            )
            
            self._last_metrics = metrics
            self.reset_error_count()
            
        except Exception as e:
            self.record_error(str(e))
        
        return metrics
    
    def cleanup(self) -> None:
        """Release resources."""
        self._initialized = False
```

## Adding Session Categories

1. Add thresholds to `SessionClassifier.THRESHOLDS` in `src/utils.py`
2. Document the detection criteria
3. Test with real workloads

### Category Template

```python
THRESHOLDS["my_category"] = {
    "gpu_utilization": (min_percent, max_percent),
    "cpu_utilization": (min_percent, max_percent),
    "ram_percent": (min_percent, max_percent),
    # Add relevant metrics
}
```

## Privacy Guidelines

When contributing, ensure:

1. **No PII Collection**: Never collect personally identifiable information
2. **No Process Monitoring**: Don't access process names or window titles
3. **No File Access**: Don't read file contents or paths
4. **No Network Sniffing**: Only collect aggregate network statistics
5. **Hash Identifiers**: Use cryptographic hashes for any identifiers

## Testing

- Write unit tests for new features
- Test on multiple platforms if possible
- Verify no privacy violations
- Check memory usage for long-running tests

## Documentation

- Update README.md for user-facing changes
- Add docstrings to new functions
- Update CHANGELOG.md
- Include examples where helpful

## Questions?

Open a discussion on GitHub or reach out to maintainers.

Thank you for contributing!
