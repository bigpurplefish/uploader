#!/usr/bin/env python3
"""
Test script to verify GUI status updates work correctly.
"""

import sys
import threading
import time
from uploader_modules.config import log_and_status

# Simple counter to track calls
call_count = 0

def mock_status(msg):
    """Mock status function that prints to console."""
    global call_count
    call_count += 1
    print(f"[{call_count}] STATUS: {msg}")

def test_direct_calls():
    """Test direct calls to log_and_status."""
    print("\n=== Test 1: Direct calls ===")
    log_and_status(mock_status, "Direct call test 1")
    log_and_status(mock_status, "Direct call test 2", "info")
    log_and_status(mock_status, "Direct call test 3 with custom UI", "info", "Custom UI message")
    print(f"Total calls: {call_count}")

def test_from_thread():
    """Test calls from a background thread (like the GUI does)."""
    global call_count
    call_count = 0
    print("\n=== Test 2: Calls from background thread ===")

    def worker():
        log_and_status(mock_status, "Thread call test 1")
        time.sleep(0.1)
        log_and_status(mock_status, "Thread call test 2")
        time.sleep(0.1)
        log_and_status(mock_status, "Thread call test 3")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()

    print(f"Total calls: {call_count}")

def test_none_status_fn():
    """Test with None status function (should not crash)."""
    print("\n=== Test 3: None status function ===")
    try:
        log_and_status(None, "This should only log, not call status")
        print("✅ None status_fn handled correctly")
    except Exception as e:
        print(f"❌ Error with None status_fn: {e}")

if __name__ == "__main__":
    print("Testing log_and_status function...")
    test_direct_calls()
    test_from_thread()
    test_none_status_fn()
    print("\n✅ All tests completed!")
