#!/usr/bin/env python3
"""Run each isolated suite with its own imports; preserve failures and test counts."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
failed = False
for relative in ['.', 'vendor/maos', 'vendor/income', 'vendor/shorts', 'vendor/day-trader']:
    print(f'\nTesting {relative}', flush=True)
    run = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                         cwd=ROOT/relative)
    failed |= run.returncode != 0
sys.exit(int(failed))
