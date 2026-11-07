"""
Global pytest and hypothesis configuration for test suite.
"""
from hypothesis import settings

# Disable wall-clock deadline flakes on Windows CI/local runs
settings.register_profile("default", deadline=None)
settings.load_profile("default")
