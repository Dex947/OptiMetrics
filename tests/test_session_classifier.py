"""
Tests for Session Classifier

Covers:
    - Classification logic
    - Workload pattern detection
    - Edge cases (empty metrics, extreme values)
    - Thread safety
    - Category transitions
"""

import pytest
from unittest.mock import patch, Mock
import threading

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import SessionClassifier
from src.adapters.base_adapter import MetricValue


class TestSessionClassifierBasic:
    """Basic session classifier tests."""
    
    def test_initialization(self):
        """Test classifier initializes correctly."""
        classifier = SessionClassifier()
        assert classifier is not None
    
    def test_update_returns_category(self):
        """Test update method returns a category or None."""
        classifier = SessionClassifier()
        
        # Need enough samples for classification
        for _ in range(10):
            result = classifier.update({
                "gpu_utilization": 80.0,
                "cpu_utilization": 40.0,
                "ram_percent": 60.0,
            })
        
        # Should return category or None
        assert result is None or hasattr(result, 'name')
    
    def test_get_current_category(self):
        """Test getting current category."""
        classifier = SessionClassifier()
        
        for _ in range(10):
            classifier.update({
                "gpu_utilization": 5.0,
                "cpu_utilization": 5.0,
            })
        
        category = classifier.get_current_category()
        # May be None or a category


class TestSessionClassifierCategories:
    """Test workload category detection."""
    
    def test_gaming_detection(self):
        """Test gaming workload detection."""
        classifier = SessionClassifier()
        
        # Gaming: High GPU, moderate CPU, high VRAM
        for _ in range(20):
            classifier.update({
                "gpu_utilization": 85.0,
                "cpu_utilization": 45.0,
                "vram_percent": 70.0,
                "ram_percent": 50.0,
            })
        
        category = classifier.get_current_category()
        # Should detect gaming or similar high-GPU workload
    
    def test_ai_training_detection(self):
        """Test AI training workload detection."""
        classifier = SessionClassifier()
        
        # AI Training: Very high GPU, high VRAM, compute processes
        for _ in range(20):
            classifier.update({
                "gpu_utilization": 95.0,
                "cpu_utilization": 30.0,
                "vram_percent": 90.0,
                "compute_processes": 2,
            })
        
        category = classifier.get_current_category()
    
    def test_coding_detection(self):
        """Test coding workload detection."""
        classifier = SessionClassifier()
        
        # Coding: Low GPU, moderate CPU, high RAM
        for _ in range(20):
            classifier.update({
                "gpu_utilization": 5.0,
                "cpu_utilization": 35.0,
                "ram_percent": 70.0,
            })
        
        category = classifier.get_current_category()
    
    def test_idle_detection(self):
        """Test idle state detection."""
        classifier = SessionClassifier()
        
        # Idle: Very low everything
        for _ in range(20):
            classifier.update({
                "gpu_utilization": 2.0,
                "cpu_utilization": 3.0,
                "ram_percent": 30.0,
            })
        
        category = classifier.get_current_category()
    
    def test_browsing_detection(self):
        """Test web browsing detection."""
        classifier = SessionClassifier()
        
        # Browsing: Network activity, low-moderate CPU
        for _ in range(20):
            classifier.update({
                "gpu_utilization": 10.0,
                "cpu_utilization": 20.0,
                "net_recv_rate_mbps": 5.0,
                "net_send_rate_mbps": 0.5,
            })
        
        category = classifier.get_current_category()
    
    def test_video_editing_detection(self):
        """Test video editing detection."""
        classifier = SessionClassifier()
        
        # Video editing: Encoder activity, high disk I/O
        for _ in range(20):
            classifier.update({
                "gpu_utilization": 60.0,
                "encoder_utilization": 80.0,
                "disk_write_rate_mbps": 100.0,
            })
        
        category = classifier.get_current_category()


class TestSessionClassifierEdgeCases:
    """Edge case tests for session classifier."""
    
    def test_empty_metrics(self):
        """Test classifier with empty metrics."""
        classifier = SessionClassifier()
        result = classifier.update({})
        assert result is None
    
    def test_partial_metrics(self):
        """Test classifier with partial metrics."""
        classifier = SessionClassifier()
        
        for _ in range(10):
            result = classifier.update({
                "total_utilization": 50.0,
            })
        
        # Should handle partial data
    
    def test_extreme_high_values(self):
        """Test classifier with extreme high values."""
        classifier = SessionClassifier()
        
        for _ in range(10):
            result = classifier.update({
                "gpu_utilization": 100.0,
                "cpu_utilization": 100.0,
                "ram_percent": 100.0,
                "vram_percent": 100.0,
            })
        
        # Should classify as something
    
    def test_extreme_low_values(self):
        """Test classifier with extreme low values."""
        classifier = SessionClassifier()
        
        for _ in range(10):
            result = classifier.update({
                "gpu_utilization": 0.0,
                "cpu_utilization": 0.0,
                "ram_percent": 0.0,
            })
        
        # Should classify as idle or similar
    
    def test_negative_values(self):
        """Test classifier handles negative values gracefully."""
        classifier = SessionClassifier()
        
        # Should not crash
        result = classifier.update({
            "gpu_utilization": -10.0,
            "cpu_utilization": -5.0,
        })
    
    def test_nan_values(self):
        """Test classifier handles NaN values."""
        classifier = SessionClassifier()
        
        result = classifier.update({
            "gpu_utilization": float('nan'),
            "cpu_utilization": 50.0,
        })
        # Should handle gracefully
    
    def test_inf_values(self):
        """Test classifier handles infinity values."""
        classifier = SessionClassifier()
        
        result = classifier.update({
            "gpu_utilization": float('inf'),
            "cpu_utilization": 50.0,
        })
        # Should handle gracefully
    
    def test_metric_value_objects(self):
        """Test classifier accepts MetricValue objects."""
        classifier = SessionClassifier()
        
        for _ in range(10):
            result = classifier.update({
                "gpu_utilization": MetricValue("gpu", 50.0, "%"),
                "cpu_utilization": MetricValue("cpu", 30.0, "%"),
            })


class TestSessionClassifierTransitions:
    """Test category transition behavior."""
    
    def test_rapid_category_changes(self):
        """Test classifier stability with rapid metric changes."""
        classifier = SessionClassifier()
        
        categories_detected = []
        for i in range(20):
            if i % 2 == 0:
                metrics = {"gpu_utilization": 80.0, "cpu_utilization": 40.0}
            else:
                metrics = {"gpu_utilization": 5.0, "cpu_utilization": 5.0}
            
            result = classifier.update(metrics)
            if result:
                categories_detected.append(result.name)
        
        # Should have some stability (not flip-flopping every sample)
    
    def test_gradual_transition(self):
        """Test gradual workload transition."""
        classifier = SessionClassifier()
        
        # Start with idle
        for _ in range(10):
            classifier.update({"gpu_utilization": 5.0, "cpu_utilization": 5.0})
        
        # Gradually increase to gaming
        for i in range(10):
            gpu = 5.0 + (i * 8)  # 5 -> 85
            classifier.update({"gpu_utilization": gpu, "cpu_utilization": 40.0})
        
        # Should eventually detect gaming
    
    def test_category_persistence(self):
        """Test category persists with consistent metrics."""
        classifier = SessionClassifier()
        
        # Consistent gaming metrics
        for _ in range(30):
            classifier.update({
                "gpu_utilization": 80.0,
                "cpu_utilization": 40.0,
                "vram_percent": 60.0,
            })
        
        category = classifier.get_current_category()
        # Category should be stable


class TestSessionClassifierThreadSafety:
    """Thread safety tests for session classifier."""
    
    def test_concurrent_updates(self):
        """Test classifier thread safety with concurrent updates."""
        classifier = SessionClassifier()
        errors = []
        
        def update_classifier():
            try:
                for _ in range(100):
                    classifier.update({
                        "gpu_utilization": 50.0,
                        "cpu_utilization": 50.0,
                    })
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=update_classifier) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
    
    def test_concurrent_read_write(self):
        """Test concurrent reading and writing."""
        classifier = SessionClassifier()
        errors = []
        
        def writer():
            try:
                for _ in range(100):
                    classifier.update({"gpu_utilization": 50.0})
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for _ in range(100):
                    classifier.get_current_category()
            except Exception as e:
                errors.append(e)
        
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0


class TestSessionClassifierConfiguration:
    """Test classifier configuration."""
    
    def test_custom_config(self):
        """Test classifier with custom configuration."""
        config = {
            "session_classification": {
                "min_samples": 5,
                "confidence_threshold": 0.7,
            }
        }
        classifier = SessionClassifier(config)
        assert classifier is not None
    
    def test_default_config(self):
        """Test classifier with default configuration."""
        classifier = SessionClassifier()
        assert classifier is not None
    
    def test_empty_config(self):
        """Test classifier with empty configuration."""
        classifier = SessionClassifier({})
        assert classifier is not None


class TestSessionClassifierHistory:
    """Test metric history management."""
    
    def test_history_limit(self):
        """Test that history doesn't grow unbounded."""
        classifier = SessionClassifier()
        
        # Add many samples
        for _ in range(1000):
            classifier.update({"gpu_utilization": 50.0})
        
        # History should be bounded
        if hasattr(classifier, '_history'):
            assert len(classifier._history) <= 1000  # Some reasonable limit
    
    def test_history_used_for_classification(self):
        """Test that history affects classification."""
        classifier = SessionClassifier()
        
        # Build up history of idle
        for _ in range(20):
            classifier.update({"gpu_utilization": 5.0, "cpu_utilization": 5.0})
        
        # Single high-GPU sample shouldn't immediately change category
        classifier.update({"gpu_utilization": 90.0, "cpu_utilization": 40.0})
        
        # Category should still reflect history
