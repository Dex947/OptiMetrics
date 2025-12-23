<div align="center">

# OptiMetrics

### Building the Future of Hardware-Aware Software Optimization

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/Dex947/OptiMetrics)
[![Contributors](https://img.shields.io/badge/Contributors-Welcome-orange.svg)](#join-the-research)

**Crowdsourced hardware telemetry for intelligent runtime optimization**

[Get Started](#quick-start) | [Why Contribute](#why-your-data-matters) | [Privacy](#privacy-commitment) | [Research Goals](#the-vision)

</div>

---

## The Problem We're Solving

Modern software treats all hardware the same way: **maximize everything, all the time.**

This approach is fundamentally broken:
- A gaming session doesn't need the same optimization as an AI training job
- A laptop on battery shouldn't behave like a desktop with unlimited power
- A 4-core CPU and a 32-core workstation need different execution strategies

**Current solutions optimize for:**
| Approach | Reality |
|----------|---------|
| Shortest path | Not always the best path |
| Maximum speed | Wastes power, generates heat |
| Brute force | Ignores hardware constraints |
| One-size-fits-all | Suboptimal for everyone |

---

## The Vision: Intent-Aware Execution

We're building a **Hardware-Intent-Aware Execution Policy Layer**—software that understands:

- **What you're trying to achieve** (latency? throughput? precision? stability?)
- **What your hardware can actually do** (thermal limits, power budget, core count)
- **What workload you're running** (gaming, AI, CAD, coding, browsing)

### The Result

Software that adapts its behavior based on **goals**, not assumptions:

| Goal | Optimization Strategy |
|------|----------------------|
| **Latency** | Prioritize response time over throughput |
| **Precision** | Favor accuracy over speed |
| **Stability** | Consistent performance over peak performance |
| **Throughput** | Maximize work completed per unit time |
| **Efficiency** | Minimize power while meeting requirements |

This isn't bloat—it's **intelligence**. Modular design means you only load what you need.

---

## Why Your Data Matters

To build this system, we need **real-world hardware telemetry** from diverse systems:

- Different CPU architectures (Intel, AMD, ARM)
- Various GPU configurations (NVIDIA, AMD, integrated)
- Range of RAM sizes and speeds
- Different storage types (SSD, NVMe, HDD)
- Real workload patterns from actual users

### What We Learn From Your Data

| Your Contribution | Research Outcome |
|-------------------|------------------|
| Gaming session metrics | Optimal GPU scheduling for frame consistency |
| AI training patterns | Efficient batch processing strategies |
| CAD workload data | Precision-focused execution policies |
| Idle/browsing patterns | Power-saving optimization triggers |
| Thermal throttling events | Proactive thermal management |

**Every contributor makes the optimization smarter for everyone.**

---

## Join the Research

### Quick Start (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/Dex947/OptiMetrics.git
cd OptiMetrics

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the collector
python src/hardware_logger.py
```

**That's it.** The tool runs in the background, collecting anonymized metrics and uploading them to our shared research database.

### What Happens Next

1. **Local Collection**: Metrics are logged to CSV files on your machine
2. **Automatic Upload**: Data syncs to our [shared research folder](https://drive.google.com/drive/folders/1KLCQmnhgXTraQvVs0I60iut9scDMCMxr) every 30 minutes
3. **Pattern Analysis**: We analyze aggregated data to identify optimization opportunities
4. **Policy Generation**: Machine learning models create hardware-specific execution policies
5. **Open Results**: All research findings are published openly

### Configuration

Customize collection in `configs/config.yaml`:

```yaml
general:
  logging_interval: 1  # Seconds between samples
  collect_cpu: true
  collect_gpu: true
  collect_ram: true
  collect_disk: true
  collect_network: true
  enable_session_classification: true

cloud:
  enabled: true  # Enable to contribute data
  upload_interval_minutes: 30
```

---

## Privacy Commitment

We take privacy seriously. Here's our commitment:

### What We Collect (Hardware Metrics Only)

<details>
<summary><b>CPU Metrics</b> - Click to expand</summary>

| Metric | Description | Unit |
|--------|-------------|------|
| `core_N_utilization` | Per-core CPU usage | % |
| `total_utilization` | Overall CPU usage | % |
| `core_N_freq_mhz` | Per-core frequency | MHz |
| `temperature` | CPU temperature (if available) | °C |
| `context_switches` | OS context switch count | count |

</details>

<details>
<summary><b>GPU Metrics</b> - Click to expand</summary>

| Metric | Description | Unit |
|--------|-------------|------|
| `utilization` | GPU core utilization | % |
| `vram_used_mb` | VRAM in use | MB |
| `temperature` | GPU temperature | °C |
| `power_watts` | Power consumption | W |
| `core_clock_mhz` | Graphics clock speed | MHz |
| `encoder_utilization` | Video encoder usage | % |

</details>

<details>
<summary><b>Memory, Disk, Network</b> - Click to expand</summary>

| Category | Metrics |
|----------|---------|
| **Memory** | RAM usage %, swap usage |
| **Disk** | I/O rates, usage per partition |
| **Network** | Bandwidth statistics (no addresses) |

</details>

### What We NEVER Collect

| Category | Guarantee |
|----------|-----------|
| **Applications** | No process names, no window titles |
| **Identity** | No usernames, no account info |
| **Files** | No file paths, no document names |
| **Network** | No IP addresses, no URLs, no connection details |
| **Input** | No keyboard/mouse data |
| **Screen** | No screenshots, no screen content |

### How We Anonymize

Your hardware is identified by a **cryptographic hash**:

```
SHA256(CPU_model + GPU_names + Motherboard) → "a3f8b2c1d4e5..."
```

This hash:
- **Cannot be reversed** to identify your hardware
- **Remains consistent** across sessions for research continuity
- **Contains no personal information**

### Data Security

- **AES-256 encryption** before upload
- **Encryption keys stay on your machine** (never uploaded)
- **OAuth2 authentication** for secure transfer
- **Open-source code** - verify everything yourself

---

## Workload Classification

OptiMetrics automatically detects what you're doing based on **hardware patterns only**:

| Category | How We Detect It |
|----------|------------------|
| **Gaming** | High GPU + moderate CPU + high VRAM |
| **AI Training** | Very high GPU + compute processes |
| **CAD/3D** | High GPU + CPU + RAM |
| **Video Editing** | Encoder activity + disk I/O |
| **Coding** | Low GPU + moderate CPU + high RAM |
| **Browsing** | Network activity + low CPU |
| **Idle** | Very low resource usage |

**No application monitoring.** We detect "gaming" from GPU patterns, not by checking if you're running a game.

---

## How to Contribute

### Option 1: Run the Collector (Easiest)

Just run OptiMetrics on your machine. Your anonymized data helps everyone.

```bash
python src/hardware_logger.py
```

Leave it running in the background. That's it.

### Option 2: Contribute Code

We welcome code contributions:

| Area | What's Needed |
|------|---------------|
| **Hardware Adapters** | AMD GPU, Intel Arc, Apple Silicon support |
| **Classifiers** | Better workload detection algorithms |
| **Analysis** | Data analysis and visualization tools |
| **Documentation** | Tutorials, translations, examples |

<details>
<summary><b>Adding a Hardware Adapter</b> - Click to expand</summary>

```python
from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue

class MyAdapter(BaseHardwareAdapter):
    def initialize(self) -> bool:
        # Setup hardware access
        return True
    
    def get_hardware_info(self) -> HardwareInfo:
        return HardwareInfo(vendor="Vendor", model="Model", identifier="id")
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        return {"metric": MetricValue(name="metric", value=42.0, unit="%")}
    
    def cleanup(self) -> None:
        pass
```

</details>

### Development Setup

```bash
pip install -r requirements.txt
pip install pytest black ruff

pytest tests/        # Run tests
black src/           # Format code
ruff check src/      # Lint
```

---

## Research Roadmap

| Phase | Goal | Status |
|-------|------|--------|
| **Phase 1** | Data collection infrastructure | ✅ Complete |
| **Phase 2** | Reach 100+ unique hardware configurations | 🔄 In Progress |
| **Phase 3** | Pattern analysis and clustering | 📋 Planned |
| **Phase 4** | ML model training for policy generation | 📋 Planned |
| **Phase 5** | Open-source execution policy layer | 📋 Planned |

### Hardware Support Roadmap

- [x] Intel/AMD x86 CPUs
- [x] NVIDIA GPUs (via pynvml)
- [ ] AMD GPUs (ROCm/pyamdgpuinfo)
- [ ] Intel Arc GPUs
- [ ] Apple Silicon (M1/M2/M3)
- [ ] ARM processors

---

## FAQ

<details>
<summary><b>Will this slow down my computer?</b></summary>

No. OptiMetrics uses <1% CPU and ~50MB RAM. It's designed to be invisible.

</details>

<details>
<summary><b>Can I see what data is being collected?</b></summary>

Yes! Check the `logs/` folder. All data is stored as readable CSV files.

</details>

<details>
<summary><b>How do I stop contributing data?</b></summary>

Set `cloud.enabled: false` in `configs/config.yaml`. Local logging continues, but nothing uploads.

</details>

<details>
<summary><b>Is this a cryptocurrency miner?</b></summary>

No. The code is 100% open source. Audit it yourself. We collect metrics, not compute cycles.

</details>

<details>
<summary><b>Who has access to the data?</b></summary>

Data uploads to a [shared Google Drive folder](https://drive.google.com/drive/folders/1KLCQmnhgXTraQvVs0I60iut9scDMCMxr). The research team analyzes aggregated patterns. Individual data points are anonymized.

</details>

---

## Project Structure

```
OptiMetrics/
├── src/
│   ├── hardware_logger.py    # Main collection script
│   ├── gdrive_uploader.py    # Cloud sync
│   ├── utils.py              # Utilities
│   └── adapters/             # Hardware adapters
├── configs/config.yaml       # Configuration
├── logs/                     # Local CSV storage
└── docs/                     # Documentation
```

## Requirements

- **Python** 3.9+
- **OS**: Windows 10/11, Linux, macOS
- **Optional**: NVIDIA GPU for GPU metrics

---

## License

Apache License 2.0 - Use it, modify it, contribute back.

---

<div align="center">

### Join Us

**Every system is unique. Every contribution matters.**

[![Star](https://img.shields.io/github/stars/Dex947/OptiMetrics?style=social)](https://github.com/Dex947/OptiMetrics)
[![Fork](https://img.shields.io/github/forks/Dex947/OptiMetrics?style=social)](https://github.com/Dex947/OptiMetrics/fork)

[Get Started](#quick-start) | [View Research Data](https://drive.google.com/drive/folders/1KLCQmnhgXTraQvVs0I60iut9scDMCMxr) | [Report Issues](https://github.com/Dex947/OptiMetrics/issues)

**Built by researchers, for the community.**

</div>
