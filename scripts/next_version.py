#!/usr/bin/env python3
"""Print the next SemVer release version (without the "v" prefix).

The version is derived from Conventional Commit messages since the latest
vX.Y.Z tag:
  "type!:" or "BREAKING CHANGE:"  -> major
  "feat:" / "feat(scope):"        -> minor
  anything else                   -> patch
With no release tag yet, the version in package.json is the first release.
"""
import json
import re
import subprocess
import sys

TAG_PATTERN = "v[0-9]*.[0-9]*.[0-9]*"
MAJOR_RE = re.compile(r"^[a-z]+(\([^)]*\))?!:|^BREAKING[ -]CHANGE:", re.MULTILINE)
MINOR_RE = re.compile(r"^feat(\([^)]*\))?:", re.MULTILINE)


def git(*args, check=True):
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=check)
    return result.stdout.strip()


def next_version():
    # Re-runs on an already released commit return the same version
    head_tags = git("tag", "--points-at", "HEAD", "--list", TAG_PATTERN, "--sort=-version:refname")
    if head_tags:
        return head_tags.splitlines()[0].removeprefix("v")

    latest_tag = git("describe", "--tags", "--abbrev=0", "--match", TAG_PATTERN, check=False)
    if not latest_tag:
        with open("package.json", encoding="utf-8") as f:
            return json.load(f)["version"]

    major, minor, patch = (int(part) for part in latest_tag.removeprefix("v").split("."))
    messages = git("log", f"{latest_tag}..HEAD", "--format=%s%n%b")

    if MAJOR_RE.search(messages):
        return f"{major + 1}.0.0"
    if MINOR_RE.search(messages):
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


if __name__ == "__main__":
    try:
        print(next_version())
    except subprocess.CalledProcessError as e:
        sys.exit(f"git {' '.join(e.cmd[1:])} failed: {e.stderr.strip()}")
