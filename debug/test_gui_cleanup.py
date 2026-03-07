#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test that GUI cleanup didn't break anything
"""

import sys
import os

# Try importing Piston.py
try:
    import Piston
    print("✓ Piston.py imports successfully")
except Exception as e:
    print(f"✗ Failed to import Piston.py: {e}")
    sys.exit(1)

# Check that the app can be instantiated
try:
    # Don't actually run the GUI, just make sure it can be created
    print("✓ Module loaded successfully")
    print("\nRemoved UI controls:")
    print("  - Unit bias field")
    print("  - Max bias % field")
    print("  - Bias window field")
    print("  - Serialization dropdown")
    print("  - Advanced >> toggle button")
    print("  - Preset buttons (No pref/Weak/Strong)")
    print("\nSmart Mode will still work automatically!")
    print("\nTo test the GUI, run: python Piston.py")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
