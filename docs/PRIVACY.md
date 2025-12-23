# Privacy Policy

## Overview

OptiMetrics is designed with privacy as a core principle. This document explains exactly what data is collected, how it's used, and what safeguards are in place.

## Data Collection

### What We Collect

OptiMetrics collects **only hardware performance metrics**:

| Category | Data Collected |
|----------|----------------|
| CPU | Utilization %, frequency, temperature, power |
| GPU | Utilization %, VRAM usage, clocks, temperature, power |
| RAM | Usage amounts and percentages |
| Disk | I/O statistics, usage per partition |
| Network | Bandwidth statistics (no addresses) |
| System | Anonymized hardware ID, detected workload category |

### What We DON'T Collect

OptiMetrics explicitly **does not collect**:

- ❌ **Process Information**: No process names, PIDs, or command lines
- ❌ **Window Data**: No window titles, screen content, or UI elements
- ❌ **User Identity**: No usernames, account names, or login info
- ❌ **File System**: No file names, paths, or document contents
- ❌ **Network Details**: No IP addresses, URLs, or connection endpoints
- ❌ **Input Data**: No keyboard, mouse, or other input device data
- ❌ **Location**: No GPS, timezone inference, or geographic data
- ❌ **Browsing History**: No web activity or application usage
- ❌ **Communications**: No emails, messages, or call data

## Hardware Identification

### How Hardware IDs Work

To enable anonymous tracking (e.g., for research or benchmarking), OptiMetrics generates a cryptographic hardware ID:

```
Input: CPU Model + GPU Names + Motherboard Info
       ↓
       SHA-256 Hash
       ↓
Output: 32-character hexadecimal string
```

**Example:**
```
Input:  "Intel Core i7-12700K|NVIDIA GeForce RTX 3080|ASUS ROG STRIX"
Output: "a3f8b2c1d4e5f6789012345678901234"
```

### Properties of Hardware IDs

1. **One-Way**: Cannot be reversed to identify hardware
2. **Consistent**: Same hardware always produces same ID
3. **Unique**: Different hardware produces different IDs
4. **Anonymous**: No personal information encoded

### What Hardware IDs Enable

- Tracking performance over time on the same machine
- Comparing metrics across different hardware configurations
- Aggregating anonymous statistics for research
- Identifying hardware-specific performance patterns

### What Hardware IDs Cannot Do

- Identify the owner of a machine
- Reveal the physical location of hardware
- Link to any personal accounts or identities
- Be used for targeted advertising

## Session Classification

### How It Works

OptiMetrics detects workload categories (gaming, coding, etc.) using **only** hardware metrics:

```
High GPU + High VRAM + Moderate CPU → "gaming"
High GPU + Very High VRAM + Compute Processes → "ai_training"
Low GPU + Moderate CPU + High RAM → "coding_development"
```

### Privacy Guarantees

- Classification uses **only** numeric hardware metrics
- No process names or application data is accessed
- No window titles or screen content is analyzed
- Categories are generic (e.g., "gaming" not "playing Cyberpunk 2077")

## Data Storage

### Local Storage

- Metrics are stored in CSV files in the `logs/` directory
- Files are named with date and hardware ID (not username)
- Old files can be automatically compressed
- Users have full control over their data

### Cloud Storage (Optional)

If cloud sync is enabled:

1. **Encryption**: Files are encrypted with AES-256-GCM before upload
2. **Key Storage**: Encryption keys remain on your local machine
3. **Authentication**: OAuth2 for secure Google Drive access
4. **No Third Parties**: Data goes directly to your cloud storage
5. **User Control**: You can disable sync at any time

## Data Retention

- **Local**: Data is retained until you delete it
- **Cloud**: Data follows your cloud provider's retention policies
- **No Central Server**: OptiMetrics has no central data collection

## Your Rights

You have complete control over your data:

1. **Access**: View all collected data in CSV files
2. **Delete**: Remove any or all log files at any time
3. **Disable**: Stop collection by closing the application
4. **Configure**: Adjust what metrics are collected
5. **Export**: Data is in standard CSV format

## Security Measures

1. **No Network by Default**: Cloud sync is disabled by default
2. **Local Processing**: All analysis happens on your machine
3. **Open Source**: Code is fully auditable
4. **Minimal Permissions**: Only requests necessary system access
5. **No Telemetry**: No data sent to OptiMetrics developers

## Changes to This Policy

Any changes to data collection will be:
- Documented in release notes
- Highlighted in the README
- Require explicit user action to enable

## Contact

For privacy concerns or questions:
- Open a GitHub issue
- Review the source code
- Contact maintainers through GitHub

---

**Last Updated**: December 2024

**Summary**: OptiMetrics collects only hardware performance metrics. No personal data, no process monitoring, no tracking. Your data stays on your machine unless you explicitly enable cloud sync to your own storage.
