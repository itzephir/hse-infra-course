#!/usr/bin/env bash
set -euo pipefail

target=${1:?Usage: deploy-push.sh dev|prod IMAGE@sha256:DIGEST}
image=${2:?Missing immutable image reference}
[[ "$target" == dev || "$target" == prod ]]
[[ "$image" =~ ^ghcr\.io/itzephir/hse-infra-course@sha256:[a-f0-9]{64}$ ]]

hw_dir=$(cd "$(dirname "$0")/.." && pwd)
namespace="hw6-relay-$target"
release_dir=$(mktemp -d)
forward_pid=
cleanup() {
    if [[ -n "$forward_pid" ]]; then
        kill "$forward_pid" 2>/dev/null || true
        wait "$forward_pid" 2>/dev/null || true
    fi
    rm -rf "$release_dir"
}
trap cleanup EXIT

# Pin a temporary copy; the checked-out Git files remain unchanged.
cp -R "$hw_dir/manifests" "$hw_dir/scripts" "$release_dir/"
python3 "$release_dir/scripts/pin-image.py" "$target" "$image"
kubectl kustomize "$release_dir/manifests/overlays/$target" > "$release_dir/release.yaml"
kubectl apply --namespace "$namespace" -f "$release_dir/release.yaml"
kubectl rollout status --namespace "$namespace" deployment/relay --timeout=180s
actual=$(kubectl get deployment/relay --namespace "$namespace" \
    -o jsonpath='{.spec.template.spec.containers[?(@.name=="website")].image}')
[[ "$actual" == "$image" ]]

kubectl port-forward --address 127.0.0.1 --namespace "$namespace" \
    service/relay 18080:80 > "$release_dir/forward.log" 2>&1 &
forward_pid=$!
curl --fail --silent --show-error --retry 20 --retry-all-errors --retry-delay 1 \
    http://127.0.0.1:18080/healthz > "$release_dir/health.txt"
[[ $(cat "$release_dir/health.txt") == relay ]]
curl --fail --silent --show-error http://127.0.0.1:18080/ > "$release_dir/index.html"
grep -q '<title>Relay' "$release_dir/index.html"
curl --fail --silent --show-error http://127.0.0.1:18080/version.json \
    > "$release_dir/version.json"
python3 -c 'import json,sys; assert json.load(sys.stdin)["name"] == "relay"' \
    < "$release_dir/version.json"
printf 'Verified %s: %s\n' "$target" "$image"
