"""
Network Hardware Adapter

Collects network interface metrics including I/O statistics,
connection counts, and throughput rates.
"""

import time
from typing import Dict, Any, Optional, List
import psutil

from .base_adapter import BaseHardwareAdapter, HardwareInfo, MetricValue


class NetworkAdapter(BaseHardwareAdapter):
    """
    Network interface metrics adapter.
    
    Collects:
        - Network I/O statistics (bytes sent/received)
        - Packet counts (sent/received)
        - Error and drop counts
        - Network throughput rates
        - Active connection counts
    
    Note: Does NOT collect IP addresses or connection details for privacy.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._interfaces: List[str] = []
        self._prev_io_counters: Optional[Any] = None
        self._prev_timestamp: Optional[float] = None
    
    def initialize(self) -> bool:
        """Initialize network monitoring."""
        try:
            # Get list of network interfaces
            net_if_addrs = psutil.net_if_addrs()
            self._interfaces = list(net_if_addrs.keys())
            
            # Initialize previous counters for rate calculation
            self._prev_io_counters = psutil.net_io_counters(pernic=False)
            self._prev_timestamp = time.time()
            
            self._initialized = True
            return True
        except Exception as e:
            self.record_error(str(e))
            return False
    
    def get_hardware_info(self) -> Optional[HardwareInfo]:
        """Get network hardware information."""
        if self._hardware_info:
            return self._hardware_info
        
        try:
            # Get interface statistics (not addresses for privacy)
            net_if_stats = psutil.net_if_stats()
            
            interface_info = []
            for iface_name, stats in net_if_stats.items():
                interface_info.append({
                    "name": iface_name,
                    "is_up": stats.isup,
                    "speed_mbps": stats.speed if stats.speed > 0 else "Unknown",
                    "mtu": stats.mtu,
                })
            
            self._hardware_info = HardwareInfo(
                vendor="System",
                model=f"Network ({len(self._interfaces)} interfaces)",
                identifier=f"NET_{len(self._interfaces)}ifaces",
                additional_info={
                    "interface_count": len(self._interfaces),
                    "interfaces": interface_info,
                }
            )
            return self._hardware_info
            
        except Exception as e:
            self.record_error(str(e))
            return None
    
    def collect_metrics(self) -> Dict[str, MetricValue]:
        """Collect current network metrics."""
        metrics = {}
        current_time = time.time()
        
        try:
            # Total Network I/O
            io_counters = psutil.net_io_counters(pernic=False)
            
            if io_counters:
                metrics["net_bytes_sent"] = MetricValue(
                    name="net_bytes_sent",
                    value=io_counters.bytes_sent,
                    unit="bytes",
                    source="psutil"
                )
                metrics["net_bytes_recv"] = MetricValue(
                    name="net_bytes_recv",
                    value=io_counters.bytes_recv,
                    unit="bytes",
                    source="psutil"
                )
                metrics["net_packets_sent"] = MetricValue(
                    name="net_packets_sent",
                    value=io_counters.packets_sent,
                    unit="count",
                    source="psutil"
                )
                metrics["net_packets_recv"] = MetricValue(
                    name="net_packets_recv",
                    value=io_counters.packets_recv,
                    unit="count",
                    source="psutil"
                )
                metrics["net_errin"] = MetricValue(
                    name="net_errin",
                    value=io_counters.errin,
                    unit="count",
                    source="psutil"
                )
                metrics["net_errout"] = MetricValue(
                    name="net_errout",
                    value=io_counters.errout,
                    unit="count",
                    source="psutil"
                )
                metrics["net_dropin"] = MetricValue(
                    name="net_dropin",
                    value=io_counters.dropin,
                    unit="count",
                    source="psutil"
                )
                metrics["net_dropout"] = MetricValue(
                    name="net_dropout",
                    value=io_counters.dropout,
                    unit="count",
                    source="psutil"
                )
                
                # Calculate throughput rates
                if self._prev_io_counters and self._prev_timestamp:
                    time_delta = current_time - self._prev_timestamp
                    if time_delta > 0:
                        send_rate = (io_counters.bytes_sent - self._prev_io_counters.bytes_sent) / time_delta
                        recv_rate = (io_counters.bytes_recv - self._prev_io_counters.bytes_recv) / time_delta
                        
                        metrics["net_send_rate_mbps"] = MetricValue(
                            name="net_send_rate_mbps",
                            value=round(send_rate * 8 / (1024**2), 2),  # Convert to Mbps
                            unit="Mbps",
                            source="psutil"
                        )
                        metrics["net_recv_rate_mbps"] = MetricValue(
                            name="net_recv_rate_mbps",
                            value=round(recv_rate * 8 / (1024**2), 2),  # Convert to Mbps
                            unit="Mbps",
                            source="psutil"
                        )
                        
                        # Also provide KB/s for easier reading at lower speeds
                        metrics["net_send_rate_kbps"] = MetricValue(
                            name="net_send_rate_kbps",
                            value=round(send_rate / 1024, 2),
                            unit="KB/s",
                            source="psutil"
                        )
                        metrics["net_recv_rate_kbps"] = MetricValue(
                            name="net_recv_rate_kbps",
                            value=round(recv_rate / 1024, 2),
                            unit="KB/s",
                            source="psutil"
                        )
                
                self._prev_io_counters = io_counters
                self._prev_timestamp = current_time
            
            # Connection counts (without exposing connection details)
            try:
                connections = psutil.net_connections(kind="all")
                
                # Count by status
                status_counts = {}
                for conn in connections:
                    status = conn.status if conn.status else "NONE"
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                metrics["net_connections_total"] = MetricValue(
                    name="net_connections_total",
                    value=len(connections),
                    unit="count",
                    source="psutil"
                )
                
                # Common connection states
                for status in ["ESTABLISHED", "LISTEN", "TIME_WAIT", "CLOSE_WAIT"]:
                    metrics[f"net_conn_{status.lower()}"] = MetricValue(
                        name=f"net_conn_{status.lower()}",
                        value=status_counts.get(status, 0),
                        unit="count",
                        source="psutil"
                    )
                    
            except (psutil.AccessDenied, PermissionError):
                # Connection info requires elevated privileges on some systems
                pass
            
            # Per-interface stats (basic, no addresses)
            io_per_nic = psutil.net_io_counters(pernic=True)
            net_if_stats = psutil.net_if_stats()
            
            for iface_name in self._interfaces:
                # Skip loopback and virtual interfaces for cleaner output
                if iface_name.lower() in ["lo", "loopback"]:
                    continue
                if iface_name.startswith(("veth", "docker", "br-", "virbr")):
                    continue
                
                safe_name = iface_name.replace(" ", "_").replace("-", "_")[:20]
                
                # Interface status
                if iface_name in net_if_stats:
                    stats = net_if_stats[iface_name]
                    metrics[f"net_{safe_name}_is_up"] = MetricValue(
                        name=f"net_{safe_name}_is_up",
                        value=1 if stats.isup else 0,
                        unit="bool",
                        source="psutil"
                    )
                    if stats.speed > 0:
                        metrics[f"net_{safe_name}_speed_mbps"] = MetricValue(
                            name=f"net_{safe_name}_speed_mbps",
                            value=stats.speed,
                            unit="Mbps",
                            source="psutil"
                        )
                
                # Interface I/O
                if iface_name in io_per_nic:
                    nic_io = io_per_nic[iface_name]
                    metrics[f"net_{safe_name}_sent_mb"] = MetricValue(
                        name=f"net_{safe_name}_sent_mb",
                        value=round(nic_io.bytes_sent / (1024**2), 2),
                        unit="MB",
                        source="psutil"
                    )
                    metrics[f"net_{safe_name}_recv_mb"] = MetricValue(
                        name=f"net_{safe_name}_recv_mb",
                        value=round(nic_io.bytes_recv / (1024**2), 2),
                        unit="MB",
                        source="psutil"
                    )
            
            self._last_metrics = metrics
            self.reset_error_count()
            
        except Exception as e:
            self.record_error(str(e))
        
        return metrics
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self._initialized = False
        self._prev_io_counters = None
        self._prev_timestamp = None
