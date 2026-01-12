#!/usr/bin/env python3
"""
Convenience script to run the MCP test server.

Usage:
    python scripts/run_mcp_test_server.py [port] [host]

Examples:
    python scripts/run_mcp_test_server.py
    python scripts/run_mcp_test_server.py 8001
    python scripts/run_mcp_test_server.py 8001 0.0.0.0
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.modules.workflow.mcp.test_server import main

if __name__ == "__main__":
    main()
