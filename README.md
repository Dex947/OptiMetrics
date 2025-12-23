# OptiMetrics

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/Dex947/OptiMetrics)

**OptiMetrics** is an open-source, privacy-focused hardware metrics collection tool that powers a **Hardware-Intent-Aware Execution Policy Layer**—a next-generation optimization system that adapts runtime behavior based on workload goals rather than assuming maximal resource usage.

## The Vision: Intent-Aware Hardware Optimization

Traditional optimization approaches focus on:
- ❌ Shortest execution path
- ❌ Maximum speed at all costs
- ❌ Brute-force resource utilization

**OptiMetrics enables a smarter approach:**
- ✅ **Goal-Aware**: Optimize for latency, precision, stability, or throughput based on actual intent
- ✅ **Hardware-Aware**: Understand real hardware capabilities and thermal/power constraints
- ✅ **Use-Case-Specific**: Different workloads (gaming vs. AI training vs. CAD) need different optimization strategies
- ✅ **Modular Architecture**: Clean separation allows targeted optimization without bloat

### How It Works

1. **Data Collection**: OptiMetrics collects hardware telemetry from diverse systems worldwide
2. **Pattern Analysis**: Workload patterns are classified and correlated with hardware configurations
3. **Policy Generation**: Machine learning models generate optimal execution policies
4. **Adaptive Runtime**: The execution layer adjusts behavior based on detected workload goals

### Why This Matters

Instead of blindly maximizing CPU/GPU usage, the system learns:
- When **latency** matters more than throughput (real-time applications)
- When **precision** is critical (scientific computing, CAD)
- When **stability** trumps speed (long-running processes)
- When **power efficiency** is the priority (mobile, thermal-constrained)

## Contributing Data

By running OptiMetrics, you contribute anonymized hardware metrics that help build better optimization policies for everyone. Data is automatically uploaded to our research database incrementally.

**Your contribution helps create software that truly understands hardware.**

## Features

- **Comprehensive Hardware Metrics**
  - CPU: Per-core utilization, frequency, temperature, power consumption
  - GPU: Utilization, VRAM usage, clocks, temperature, power, encoder/decoder activity
  - RAM: Usage, swap/page file, memory allocation patterns
  - Disk: I/O statistics, throughput rates, usage per partition
  - Network: Bandwidth, packet counts, connection statistics

- **Privacy-First Design**
  - Cryptographic hardware IDs for anonymized tracking
  - No process names, window titles, or personal data collected
  - No network addresses or file paths logged
  - All identifiable hardware info is hashed

- **Automatic Session Classification**
  - Detects workload patterns: gaming, AI training, CAD, graphics design, coding, browsing, etc.
  - Based purely on system metrics—no application monitoring
  - Configurable confidence thresholds

- **Automatic Cloud Sync**
  - Incremental upload to central research database
  - AES-256 encryption for secure transfer
  - Minimal bandwidth usage with delta compression

- **Efficient Data Storage**
  - Per-second resolution logging
  - Rolling daily log files with size limits
  - Delta filtering to reduce file size (~5MB/hour)
  - Automatic compression of old logs

- **Modular Architecture**
  - Clean separation of adapters, classifiers, and core logic
  - Easy to extend with new hardware support
  - No bloat—only load what you need

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Dex947/OptiMetrics.git
cd OptiMetrics

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```bash
# Run the logger
python src/hardware_logger.py

# Run with verbose output
python src/hardware_logger.py --verbose

# Run in test mode (10 seconds)
python src/hardware_logger.py --test

# Use custom config
python src/hardware_logger.py --config path/to/config.yaml
```

### Configuration

Edit `configs/config.yaml` to customize:

```yaml
general:
  logging_interval: 1  # Seconds between samples
  collect_cpu: true
  collect_gpu: true
  collect_ram: true
  collect_disk: true
  collect_network: true
  enable_session_classification: true

logging:
  log_directory: "logs"
  rolling_logs: true
  max_file_size_mb: 50
  enable_delta_filtering: true
  delta_threshold_percent: 2.0

cloud:
  enabled: false
  provider: "gdrive"
  encrypt_before_upload: true
```

## Data Collected

### CPU Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `core_N_utilization` | Per-core CPU usage | % |
| `total_utilization` | Overall CPU usage | % |
| `core_N_freq_mhz` | Per-core frequency | MHz |
| `temperature` | CPU temperature (if available) | °C |
| `context_switches` | OS context switch count | count |
| `interrupts` | Hardware interrupt count | count |

### GPU Metrics (NVIDIA)
| Metric | Description | Unit |
|--------|-------------|------|
| `utilization` | GPU core utilization | % |
| `memory_utilization` | Memory controller usage | % |
| `vram_used_mb` | VRAM in use | MB |
| `vram_percent` | VRAM usage percentage | % |
| `temperature` | GPU temperature | °C |
| `power_watts` | Power consumption | W |
| `core_clock_mhz` | Graphics clock speed | MHz |
| `memory_clock_mhz` | Memory clock speed | MHz |
| `fan_speed` | Fan speed | % |
| `encoder_utilization` | Video encoder usage | % |
| `decoder_utilization` | Video decoder usage | % |
| `compute_processes` | Active compute processes | count |

### Memory Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `ram_used_mb` | RAM in use | MB |
| `ram_available_mb` | Available RAM | MB |
| `ram_percent` | RAM usage percentage | % |
| `swap_used_mb` | Swap/page file in use | MB |
| `swap_percent` | Swap usage percentage | % |

### Disk Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `disk_X_used_gb` | Disk space used | GB |
| `disk_X_percent` | Disk usage percentage | % |
| `disk_read_rate_mbps` | Read throughput | MB/s |
| `disk_write_rate_mbps` | Write throughput | MB/s |
| `disk_read_count` | Read operations | count |
| `disk_write_count` | Write operations | count |

### Network Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `net_bytes_sent` | Total bytes sent | bytes |
| `net_bytes_recv` | Total bytes received | bytes |
| `net_send_rate_mbps` | Upload speed | Mbps |
| `net_recv_rate_mbps` | Download speed | Mbps |
| `net_connections_total` | Active connections | count |

## Session Classification

OptiMetrics automatically detects workload categories based on hardware metric patterns:

| Category | Detection Criteria |
|----------|-------------------|
| **gaming** | High GPU (60-100%), moderate CPU, high VRAM |
| **ai_training** | Very high GPU (80-100%), high VRAM, compute processes |
| **cad_3d_modeling** | High GPU + CPU, high RAM usage |
| **graphics_design** | Moderate GPU, variable CPU, image processing patterns |
| **video_editing** | High encoder usage, high disk I/O |
| **coding_development** | Low GPU, moderate CPU, high RAM |
| **document_editing** | Low resource usage overall |
| **web_browsing** | Network activity, low-moderate CPU |
| **idle** | Very low resource usage |
| **system_maintenance** | High disk I/O, low GPU |

**Important:** Classification is based **only** on system metrics. No process names, window titles, or application data is ever collected.

## Security & Privacy

### What We Collect
- Hardware performance metrics (CPU, GPU, RAM, disk, network)
- Anonymized hardware identifier (cryptographic hash)
- Detected workload category

### What We DON'T Collect
- ❌ Process names or application data
- ❌ Window titles or screen content
- ❌ User names or account information
- ❌ File paths or document names
- ❌ Network addresses or connection details
- ❌ Keyboard/mouse input
- ❌ Any personally identifiable information

### Hardware ID Generation

The hardware ID is a SHA-256 hash of hardware identifiers:
```
SHA256(CPU_model + GPU_names + Motherboard_info) → First 32 characters
```

This creates a unique, consistent identifier that:
- Cannot be reversed to identify specific hardware
- Remains stable across reboots
- Allows anonymous tracking for research purposes

### Cloud Upload Security

When cloud sync is enabled:
- Files are encrypted with AES-256-GCM before upload
- Encryption keys are stored locally (never uploaded)
- OAuth2 authentication for Google Drive
- No data is shared with third parties

## Contributing

We welcome contributions! Here's how you can help:

### Adding New Hardware Adapters

1. Create a new adapter in `src/adapters/`:

```python
from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue

class MyCustomAdapter(BaseHardwareAdapter):
    def initialize(self) -> bool:
        # Initialize hardware access
        return True
    
    def get_hardware_info(self) -> HardwareInfo:
        return HardwareInfo(
            vendor="Vendor",
            model="Model",
            identifier="unique_id"
        )
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        return {
            "my_metric": MetricValue(
                name="my_metric",
                value=42.0,
                unit="%",
                source="my_adapter"
            )
        }
    
    def cleanup(self) -> None:
        pass
```

2. Register in `src/adapters/__init__.py`
3. Add initialization in `hardware_logger.py`

### Adding Session Classifiers

Extend the `SessionClassifier` class in `src/utils.py`:

```python
# Add new category thresholds
THRESHOLDS["my_category"] = {
    "gpu_utilization": (min, max),
    "cpu_utilization": (min, max),
    # ... other metrics
}
```

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install pytest black ruff

# Run tests
pytest tests/

# Format code
black src/
ruff check src/
```

## Project Structure

```
OptiMetrics/
├── src/
│   ├── __init__.py
│   ├── hardware_logger.py    # Main logging script
│   ├── utils.py              # Utilities, crypto ID, cloud upload
│   └── adapters/
│       ├── __init__.py
│       ├── base_adapter.py   # Abstract base class
│       ├── cpu_adapter.py    # CPU metrics
│       ├── nvidia_adapter.py # NVIDIA GPU metrics
│       ├── memory_adapter.py # RAM metrics
│       ├── disk_adapter.py   # Storage metrics
│       └── network_adapter.py# Network metrics
├── configs/
│   └── config.yaml           # Configuration file
├── logs/                     # CSV log storage
├── docs/                     # Documentation
├── LICENSE                   # Apache 2.0
├── README.md
├── requirements.txt
└── .gitignore
```

## Requirements

- **Python**: 3.9 or higher
- **OS**: Windows 10/11 (primary), Linux/macOS (partial support)
- **GPU**: NVIDIA GPU with drivers for GPU metrics (optional)

### Dependencies

| Package | Purpose |
|---------|---------|
| psutil | System metrics |
| pynvml | NVIDIA GPU metrics |
| GPUtil | GPU utilities |
| py-cpuinfo | CPU information |
| PyYAML | Configuration |
| google-api-python-client | Google Drive upload |
| cryptography | File encryption |

## Auto-Start on Boot (Windows)

To automatically start logging on system boot:

1. Create a shortcut to `run_logger.bat`
2. Press `Win + R`, type `shell:startup`
3. Move the shortcut to the Startup folder

Or use Task Scheduler for more control.

## Troubleshooting

### No GPU metrics
- Ensure NVIDIA drivers are installed
- Install pynvml: `pip install pynvml`
- Check GPU is detected: `nvidia-smi`

### Permission errors on Linux
- Some metrics require root access
- Run with sudo or add user to appropriate groups

### High CPU usage
- Increase `logging_interval` in config
- Enable `enable_delta_filtering`
- Reduce number of collected metrics

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [psutil](https://github.com/giampaolo/psutil) - Cross-platform system monitoring
- [pynvml](https://github.com/gpuopenanalytics/pynvml) - NVIDIA Management Library bindings
- [py-cpuinfo](https://github.com/workhorsy/py-cpuinfo) - CPU information

## Roadmap

- [ ] AMD GPU support (ROCm/pyamdgpuinfo)
- [ ] Intel Arc GPU support
- [ ] macOS Metal GPU metrics
- [ ] Real-time dashboard
- [ ] Data export to InfluxDB/Prometheus
- [ ] Mobile app for remote monitoring
- [ ] Machine learning-based anomaly detection

---

**Made with ❤️ by the OptiMetrics community**
