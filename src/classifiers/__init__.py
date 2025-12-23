"""
Session Classifiers Module

This module contains workload classification algorithms that detect
session categories based on hardware metric patterns.

Available Classifiers:
    - RuleBasedClassifier: Threshold-based classification (default)
    - (Future) MLClassifier: Machine learning-based classification
"""

from src.utils import SessionClassifier, SessionCategory

__all__ = ["SessionClassifier", "SessionCategory"]
