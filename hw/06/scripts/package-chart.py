"""Bake a tested image digest into a versioned copy of the Helm chart."""

import re
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 5:
        raise SystemExit("Usage: package-chart.py SOURCE_SHA IMAGE CHART_VERSION OUTPUT_DIR")
    source_sha, image, version, output_dir = sys.argv[1:]
    match = re.fullmatch(r"ghcr\.io/itzephir/hse-infra-course@(sha256:[a-f0-9]{64})", image)
    if not match or not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise SystemExit("Expected a full source SHA and immutable image")
    if not re.fullmatch(r"0\.[0-9]+\.[0-9]+", version):
        raise SystemExit("Expected chart version 0.<run ID>.<attempt>")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    chart = output / "relay"
    shutil.copytree(Path(__file__).resolve().parents[1] / "chart", chart)
    path = chart / "values.yaml"
    content = path.read_text()
    content, sources = re.subn(r"(?m)^sourceRevision: local$", f"sourceRevision: {source_sha}", content)
    content, digests = re.subn(r'(?m)^  digest: ""$', f"  digest: {match[1]}", content)
    if sources != 1 or digests != 1:
        raise SystemExit("Unexpected chart defaults")
    path.write_text(content)
    subprocess.run(["helm", "lint", str(chart), "--strict"], check=True)
    subprocess.run(["helm", "package", str(chart), "--version", version, "--app-version", source_sha, "--destination", str(output)], check=True)


if __name__ == "__main__":
    main()
