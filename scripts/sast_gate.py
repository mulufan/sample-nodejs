#!/usr/bin/env python3
"""Fail CI on CRITICAL Semgrep findings.

Reads the Semgrep JSON report, writes every finding to the GitHub Actions job
summary and exits non-zero on CRITICAL findings. Fails closed: a missing or
invalid report, or any scan error, also fails.
Usage: scripts/sast_gate.py [semgrep.json]
"""
import json
import os
import sys


def load_report(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"::error::Cannot read Semgrep report {path}: {e}")


def write_summary(results):
    lines = ["### Semgrep findings", "| Severity | Location | Rule |", "|---|---|---|"]
    for r in results:
        lines.append(f"| {r['extra']['severity']} | {r['path']}:{r['start']['line']} | {r['check_id']} |")
    summary = "\n".join(lines) + "\n"

    # Outside GitHub Actions (local runs) print the summary instead
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(summary)
    else:
        print(summary)


def main():
    report = load_report(sys.argv[1] if len(sys.argv) > 1 else "semgrep.json")

    if report.get("errors"):
        for error in report["errors"]:
            print(f"::error::Semgrep scan error: {error.get('message', error)}")
        sys.exit("FAIL Semgrep reported scan errors")

    results = report["results"]
    write_summary(results)

    critical = [r for r in results if r["extra"]["severity"] == "CRITICAL"]
    for r in critical:
        print(f"::error file={r['path']},line={r['start']['line']}::{r['check_id']}: {r['extra']['message']}")
    if critical:
        sys.exit(f"FAIL {len(critical)} CRITICAL finding(s)")
    print(f"OK   No CRITICAL findings ({len(results)} reported)")


if __name__ == "__main__":
    main()
