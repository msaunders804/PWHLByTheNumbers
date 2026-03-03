#!/usr/bin/env python3
"""
Quick runner for the PWHL Analytics Pipeline
This is a convenience wrapper that runs scripts/pipeline.py
"""

import subprocess
import sys
import os

# Change to project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Run the pipeline from scripts directory
result = subprocess.run([sys.executable, "scripts/pipeline.py"] + sys.argv[1:])
sys.exit(result.returncode)
