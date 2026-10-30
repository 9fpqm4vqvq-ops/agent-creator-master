#!/usr/bin/env python3
"""Run the IOI package without pip installation from project root."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ioi.cli import main
if __name__=='__main__':raise SystemExit(main())
