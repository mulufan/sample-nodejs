#!/usr/bin/env python3
"""Publish the scanned Docker image to GHCR without overwriting a release.

Verifies the loaded image has the image ID recorded at scan time, then pushes
it as <version> and sha-<short commit sha>. A version tag is never overwritten:
if both tags already point to one digest (re-run of the same commit) the push
is skipped; any other existing version tag fails.
Usage: scripts/ghcr_publish.py <local-image> <registry-image> <version> <scanned-image-id>
"""
import os
import subprocess
import sys


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"::error::docker {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def remote_digest(ref):
    """Return the manifest digest of ref, or "" if the tag does not exist.

    Authenticated GHCR answers 404 (buildx: "<ref>: not found") for a missing
    tag and for a package that does not exist yet. Any other failure (auth,
    network, registry) fails closed so a tag is never pushed blindly.
    """
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{.Manifest.Digest}}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    error = result.stderr.strip()
    if error.endswith(f"{ref}: not found"):
        return ""
    sys.exit(f"::error::Cannot look up {ref}: {error}")


def write_summary(text):
    # Outside GitHub Actions (local runs) print the summary instead
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


def main():
    # sys argv should contain "$IMAGE_NAME:$VERSION" "$REGISTRY_IMAGE" "$VERSION" "$IMAGE_ID"
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    local_image, registry_image, version, scanned_id = sys.argv[1:]
    commit = os.environ.get("GITHUB_SHA")
    if not commit:
        sys.exit("::error::GITHUB_SHA is not set")

    loaded_id = docker("image", "inspect", "--format", "{{.Id}}", local_image)
    if loaded_id != scanned_id:
        sys.exit(f"::error::Image ID mismatch: scanned '{scanned_id}', loaded '{loaded_id}'")
    print(f"OK   Verified image ID {loaded_id}")

    sha_tag = f"sha-{commit[:7]}"
    version_digest = remote_digest(f"{registry_image}:{version}")
    if version_digest:
        if version_digest == remote_digest(f"{registry_image}:{sha_tag}"):
            print(f"SKIP {registry_image}:{version} already published from this commit")
            return
        sys.exit(f"::error::{registry_image}:{version} already exists from another commit")

    # sha tag first, so a partial push still re-runs as the same commit
    for tag in (sha_tag, version):
        docker("tag", local_image, f"{registry_image}:{tag}")
        docker("push", f"{registry_image}:{tag}")
        print(f"OK   Pushed {registry_image}:{tag}")

    # Both tags must resolve to the one image just pushed
    digest = remote_digest(f"{registry_image}:{version}")
    if not digest or digest != remote_digest(f"{registry_image}:{sha_tag}"):
        sys.exit(f"::error::{registry_image}:{version} and {sha_tag} do not resolve to one digest")
    write_summary(f"Published `{registry_image}:{version}` (`{sha_tag}`): `{digest}`")


if __name__ == "__main__":
    main()
