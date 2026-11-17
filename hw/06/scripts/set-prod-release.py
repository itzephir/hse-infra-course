"""Write the tested main image and its provenance into the prod manifests."""

import re
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 4:
        raise SystemExit("Usage: set-prod-release.py SOURCE_SHA IMAGE GITHUB_RUN_ID")
    source_sha, image, run_id = sys.argv[1:]
    match = re.fullmatch(r"ghcr\.io/itzephir/hse-infra-course@(sha256:[a-f0-9]{64})", image)
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha) or not match or not run_id.isdigit():
        raise SystemExit("Expected a full source SHA, immutable HW6 image and numeric run ID")

    overlay = Path(__file__).resolve().parents[1] / "manifests/overlays/prod"
    path = overlay / "kustomization.yaml"
    content, count = re.subn(r"(?m)^    digest: .+$", f"    digest: {match[1]}", path.read_text())
    if count != 1:
        raise SystemExit("Expected exactly one pinned prod image")
    release = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: relay
spec:
  template:
    metadata:
      annotations:
        relay/source-revision: "{source_sha}"
        relay/build-run: "https://github.com/itzephir/hse-infra-course/actions/runs/{run_id}"
'''
    path.write_text(content)
    (overlay / "release.yaml").write_text(release)


if __name__ == "__main__":
    main()
