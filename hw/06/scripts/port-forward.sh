#!/usr/bin/env bash
set -euo pipefail
pids=()
cleanup() {
    for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
    wait || true
}
trap cleanup EXIT
kubectl --context hw6 --namespace hw6-relay-dev port-forward \
    --address 127.0.0.1 service/relay 18080:80 &
pids+=("$!")
kubectl --context hw6 --namespace hw6-relay-prod port-forward \
    --address 127.0.0.1 service/relay 18081:80 &
pids+=("$!")
kubectl --context hw6 --namespace argocd port-forward \
    --address 127.0.0.1 service/argocd-server 18443:443 &
pids+=("$!")
printf 'dev: http://127.0.0.1:18080\nprod: http://127.0.0.1:18081\nArgo CD: https://127.0.0.1:18443\n'
wait
