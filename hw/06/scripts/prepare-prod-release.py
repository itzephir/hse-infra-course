"""Prepare a reviewable prod digest update from a successful main CI run."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY = "itzephir/hse-infra-course"


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        raise SystemExit("Usage: prepare-prod-release.py GITHUB_RUN_ID")
    run_id = sys.argv[1]
    run = json.loads(subprocess.check_output([
        "gh", "api", f"repos/{REPOSITORY}/actions/runs/{run_id}",
    ], text=True))
    if run["status"] != "completed" or run["conclusion"] != "success":
        raise SystemExit("Only a successful completed CI run can be selected")
    if run["head_branch"] != "main" or run["event"] not in {"push", "workflow_dispatch"}:
        raise SystemExit("Prod candidates must come from main")
    if run["path"] != ".github/workflows/hw6-image.yml":
        raise SystemExit("Expected the HW6 build workflow")
    source_sha = run["head_sha"]
    with tempfile.TemporaryDirectory(prefix="hw6-prod-release-") as temporary:
        subprocess.run([
            "gh", "run", "download", run_id, "--repo", REPOSITORY,
            "--name", f"hw6-release-{source_sha}", "--dir", temporary,
        ], check=True)
        values = {}
        for line in (Path(temporary) / "release.env").read_text().splitlines():
            key, value = line.split("=", 1)
            if key in values:
                raise SystemExit("Duplicate key in CI artifact")
            values[key] = value
    if values.get("SOURCE_SHA") != source_sha or not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise SystemExit("Artifact source SHA does not match the CI run")
    image = values.get("IMAGE", "")
    match = re.fullmatch(r"ghcr\.io/itzephir/hse-infra-course@(sha256:[a-f0-9]{64})", image)
    if not match:
        raise SystemExit("Expected an immutable image digest in the CI artifact")

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
        relay/build-run: "https://github.com/{REPOSITORY}/actions/runs/{run_id}"
'''
    path.write_text(content)
    (overlay / "release.yaml").write_text(release)
    print(f"Prepared prod candidate: {image}")
    print(f"Source: {source_sha}; build: https://github.com/{REPOSITORY}/actions/runs/{run_id}")
    print("Review the manifest diff and commit it through the main review process")


if __name__ == "__main__":
    main()
