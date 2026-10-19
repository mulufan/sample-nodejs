#!/usr/bin/env python3
"""Smoke-test a running instance of the app.

Waits for /ready, then checks the main endpoints return the expected content.
Usage: scripts/smoke_test.py [base-url]
"""
import sys
import time
import urllib.error
import urllib.request

CHECKS = [
    ("/ready", "Ready"),
    ("/live", "Alive"),
    ("/my-app", "Hello, World!"),
    ("/metrics", "root_access_total"),
]


def get(url):
    # Raises on connection errors and HTTP status >= 400
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def wait_until_ready(base_url, timeout=30):
    # Wait up to 30s for the app to accept requests
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            get(f"{base_url}/ready")
            return
        except (urllib.error.URLError, OSError):
            time.sleep(1)


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    wait_until_ready(base_url)

    for path, expected in CHECKS:
        try:
            body = get(f"{base_url}{path}")
        except (urllib.error.URLError, OSError) as e:
            sys.exit(f"FAIL {path}: {e}")
        if expected not in body:
            sys.exit(f"FAIL {path}: expected response to contain '{expected}'")
        print(f"OK   {path}")


if __name__ == "__main__":
    main()
