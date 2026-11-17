"""Pin one GitOps environment to the immutable image reported by CI."""

import re
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in {"dev", "prod"}:
        raise SystemExit("Usage: pin-image.py dev|prod IMAGE@sha256:DIGEST")

    environment, image = sys.argv[1:]
    match = re.fullmatch(
        r"(ghcr\.io/itzephir/hse-infra-course)@(sha256:[a-f0-9]{64})", image
    )
    if not match:
        raise SystemExit("Expected ghcr.io/itzephir/hse-infra-course@sha256:<64 hex digits>")

    path = (
        Path(__file__).resolve().parents[1]
        / "manifests/overlays"
        / environment
        / "kustomization.yaml"
    )
    content, count = re.subn(
        r"(?m)^    (?:newTag|digest): .+$",
        f"    digest: {match[2]}",
        path.read_text(),
    )
    if count != 1:
        raise SystemExit("Expected exactly one image version in the overlay")

    path.write_text(content)
    print(f"Pinned {environment} to {image}")


if __name__ == "__main__":
    main()
