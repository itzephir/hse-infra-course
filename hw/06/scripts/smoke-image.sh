#!/usr/bin/env bash
set -euo pipefail
image=${1:?Usage: smoke-image.sh IMAGE EXPECTED_REVISION [PLATFORM ...]}
revision=${2:?Expected source revision is required}
shift 2
if [[ $# -eq 0 ]]; then set -- linux/amd64; fi
work_dir=$(mktemp -d)
container="hw6-smoke-$$"
cleanup() {
    result=$?
    if [[ "$result" -ne 0 ]]; then docker logs "$container" >&2 2>/dev/null || true; fi
    docker rm -f "$container" >/dev/null 2>&1 || true
    rm -rf "$work_dir"
}
trap cleanup EXIT
for platform in "$@"; do
    docker run --platform "$platform" --detach --name "$container" \
        --read-only --tmpfs /tmp:rw,nosuid,size=32m \
        --publish 127.0.0.1:18090:8080 "$image"
    curl --fail --silent --show-error --retry 30 --retry-all-errors --retry-delay 1 \
        http://127.0.0.1:18090/healthz > "$work_dir/health"
    [[ $(cat "$work_dir/health") == relay ]]
    curl -fsS http://127.0.0.1:18090/ > "$work_dir/index.html"
    grep -q '<title>Relay' "$work_dir/index.html"
    curl -fsS http://127.0.0.1:18090/style.css > "$work_dir/style.css"
    test -s "$work_dir/style.css"
    curl -fsS http://127.0.0.1:18090/mark.svg > "$work_dir/mark.svg"
    curl -fsS http://127.0.0.1:18090/version.json > "$work_dir/version.json"
    python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["name"] == "relay"; assert data["revision"] == sys.argv[1]' \
        "$revision" < "$work_dir/version.json"
    docker rm -f "$container" >/dev/null
    printf 'Passed HTTP smoke tests: %s %s\n' "$platform" "$image"
done
