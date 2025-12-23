# Changelog

All notable changes to OptiMetrics will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- AMD GPU support via ROCm/pyamdgpuinfo
- Intel Arc GPU metrics
- macOS Metal GPU support
- Real-time dashboard UI
- InfluxDB/Prometheus export
- Anomaly detection

## [1.0.0] - 2024-12-23

### Added
- Initial release of OptiMetrics
- **CPU Metrics Collection**
  - Per-core utilization and frequency
  - Temperature monitoring (where available)
  - Context switches and interrupts
  - Load averages (Unix systems)

- **NVIDIA GPU Metrics Collection**
  - Utilization and memory usage
  - Temperature and power consumption
  - Core and memory clock speeds
  - Fan speed and PCIe throughput
  - Encoder/decoder utilization
  - Process counts

- **Memory Metrics Collection**
  - RAM usage and availability
  - Swap/page file statistics
  - Buffer and cache info (Linux)

- **Disk Metrics Collection**
  - Per-partition usage
  - I/O statistics and throughput
  - Read/write counts and times

- **Network Metrics Collection**
  - Bandwidth statistics
  - Packet counts
  - Error and drop counts
  - Connection statistics

- **Privacy Features**
  - Cryptographic hardware ID generation
  - No personal data collection
  - Configurable anonymization

- **Session Classification**
  - Automatic workload detection
  - Categories: gaming, AI training, CAD, graphics, video editing, coding, documents, browsing, idle
  - Confidence scoring

- **Data Management**
  - Per-second resolution logging
  - Rolling daily CSV files
  - Delta filtering for size reduction
  - Automatic log compression

- **Cloud Integration**
  - Google Drive upload support
  - AES-256 encryption before upload
  - OAuth2 authentication

- **Modular Architecture**
  - Base adapter interface
  - Easy extension for new hardware
  - Pluggable classifiers

### Security
- All hardware identifiers are cryptographically hashed
- No process names or window titles collected
- No network addresses logged
- Optional encryption for cloud uploads

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 1.0.0 | 2024-12-23 | Initial release |
