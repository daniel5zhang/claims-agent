#!/usr/bin/env python3
"""POC: 验证 3 个核心技术假设"""
import subprocess
import sys

tests = [
    ("test1_tool_use_loop.py", "Tool use loop (openai + DashScope)"),
    ("test2_sqlite_vec.py", "sqlite-vec drug matching"),
    ("test3_websocket.py", "Django Channels WebSocket"),
]

passed = 0
failed = 0

for script, desc in tests:
    print(f"\n{'='*60}")
    print(f"Running: {desc}")
    print(f"{'='*60}")
    r = subprocess.run([sys.executable, f"poc/{script}"], capture_output=False, timeout=60)
    if r.returncode == 0:
        passed += 1
    else:
        failed += 1
        print(f"  -> FAILED (exit code {r.returncode})")

print(f"\n{'='*60}")
if failed == 0:
    print("ALL 3 TESTS PASSED")
else:
    print(f"{passed} passed, {failed} failed")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
