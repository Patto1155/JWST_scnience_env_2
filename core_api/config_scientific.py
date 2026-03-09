"""
Configuration for Scientific Research Agent.

Use this to enable deeper thinking and scientific method.
"""

# To enable scientific agent mode, set this to True
USE_SCIENTIFIC_AGENT = True

# Increase max steps for deeper investigations
SCIENTIFIC_MAX_STEPS = 30  # vs default 50

# Allow more cost for thorough analysis
SCIENTIFIC_MAX_COST = 15.0  # vs default 10.0

# Scientific method parameters
REQUIRE_REFLECTION = True  # Force agent to reflect after observations
MIN_OBSERVATIONS_BEFORE_CONCLUSION = 3  # Minimum measurements before finishing
ENCOURAGE_HYPOTHESIS_TESTING = True  # Prompt for hypothesis formation
