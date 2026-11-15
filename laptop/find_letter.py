#!/usr/bin/env python3
"""Moved to copilot/find_letter.py, because the board runs copilot/ only. Kept so old imports work."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from copilot.find_letter import _norm, find_letter  # noqa: E402,F401
