#!/usr/bin/env python3
"""Set image.tag in a Helm values file to a release version (GitOps deploy).

Only the tag line inside the top-level "image:" block is rewritten, so the
rest of the file (comments, order, quoting, line endings) is preserved.
The tag only moves forward: an equal or lower version leaves the file
unchanged, so re-runs and late runs never roll a deployment back.
Fails closed if the version or the current tag is not X.Y.Z, or no tag is found.
Usage: scripts/gitops_update.py <values-file> <version>
"""
import os
import re
import sys

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# Top-level "image:" key, then an indented "tag:" line inside its block
IMAGE_RE = re.compile(r"^image:\s*(#.*)?$")
TAG_RE = re.compile(r"^(?P<indent>\s+)tag:(?P<space>\s*)(?P<quote>[\"']?)(?P<value>[^\"'\s#]*)(?P=quote)(?P<rest>\s*(#.*)?)$")


def parse_version(value, what):
    match = SEMVER_RE.match(value)
    if not match:
        sys.exit(f"::error::{what} '{value}' is not a X.Y.Z version")
    return tuple(int(part) for part in match.groups())


def find_tag_line(lines):
    """Return the index of image.tag, or None."""
    in_image = False
    for i, line in enumerate(lines):
        text = line.rstrip("\r\n")
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        if not text[0].isspace():
            # A new top-level key opens or closes the image block
            in_image = bool(IMAGE_RE.match(text))
        elif in_image and TAG_RE.match(text):
            return i
    return None


def write_summary(text):
    # Outside GitHub Actions (local runs) print the summary instead
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


def main():
    # "$VALUES_FILE" "$VERSION"
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    values_file, version = sys.argv[1:]
    new = parse_version(version, "Version")

    # newline="" keeps the file's own line endings on read and write
    with open(values_file, encoding="utf-8", newline="") as f:
        lines = f.readlines()

    index = find_tag_line(lines)
    if index is None:
        sys.exit(f"::error::No image.tag found in {values_file}")
    line = lines[index]
    ending = line[len(line.rstrip("\r\n")):]
    match = TAG_RE.match(line.rstrip("\r\n"))
    current_tag = match["value"]
    current = parse_version(current_tag, "Current tag")

    if new <= current:
        print(f"SKIP {values_file}: image.tag {current_tag} is not older than {version}")
        return

    quote = match["quote"] or '"'
    lines[index] = f'{match["indent"]}tag:{match["space"] or " "}{quote}{version}{quote}{match["rest"]}{ending}'
    with open(values_file, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)
    write_summary(f"GitOps: `{values_file}` image.tag `{current_tag}` -> `{version}`")


if __name__ == "__main__":
    main()
