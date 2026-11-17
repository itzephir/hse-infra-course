"""Select an immutable source revision and image for one GitOps Application."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 6 or sys.argv[1] not in {"dev", "prod"}:
        raise SystemExit("Usage: publish-gitops.py dev|prod IMAGE SOURCE_SHA SOURCE_DIR GITOPS_DIR")
    target, image, source_sha, source_dir, gitops_dir = sys.argv[1:]
    if not re.fullmatch(r"ghcr\.io/itzephir/hse-infra-course@sha256:[a-f0-9]{64}", image):
        raise SystemExit("Expected an immutable hse-infra-course image")
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise SystemExit("Expected a full source commit SHA")
    source = Path(source_dir).resolve()
    deployment = Path(gitops_dir).resolve()
    actual_sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual_sha != source_sha:
        raise SystemExit("Source checkout does not match the selected release")

    template = (source / "hw/06/argocd" / f"{target}.yaml").read_text()
    template, revisions = re.subn(r"(?m)^    targetRevision: .+$", f"    targetRevision: {source_sha}", template)
    template, images = re.subn(r"(?m)^        - relay=.+$", f"        - relay={image}", template)
    if revisions != 1 or images != 1:
        raise SystemExit("Expected one revision and one image in the Application template")

    (deployment / "applications").mkdir(parents=True, exist_ok=True)
    (deployment / "applications" / f"{target}.yaml").write_text(template)
    (deployment / ".releases").mkdir(exist_ok=True)
    metadata = {
        "source_sha": source_sha,
        "source_branch": os.environ.get("SOURCE_BRANCH", "bootstrap"),
        "image": image,
        "run_url": f"https://github.com/itzephir/hse-infra-course/actions/runs/{os.environ['GITHUB_RUN_ID']}" if "GITHUB_RUN_ID" in os.environ else None,
    }
    (deployment / ".releases" / f"{target}.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Selected {target}: source {source_sha}, image {image}")


if __name__ == "__main__":
    main()
