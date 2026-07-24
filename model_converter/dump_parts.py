#!/usr/bin/env python3
# ABOUTME: Backwards-compatibility shim — forwards to build_configurator.py in scaffold-only mode.
# ABOUTME: Use build_configurator.py for new work; this preserves the legacy CLI for existing scripts.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_configurator import main

if __name__ == "__main__":
    if "--scaffold-only" not in sys.argv:
        sys.argv.insert(1, "--scaffold-only")
    sys.exit(main())
