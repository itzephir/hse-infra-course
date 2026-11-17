#!/usr/bin/env bash
set -euo pipefail
profile=hw6
argocd_version=v3.6.1
hw_dir=$(cd "$(dirname "$0")/.." && pwd)

minikube start --profile "$profile" --driver=docker --container-runtime=containerd \
    --cpus=2 --memory=4096 --kubernetes-version=v1.37.0 --keep-context
kubectl --context "$profile" create namespace argocd --dry-run=client -o yaml \
    | kubectl --context "$profile" apply -f -
kubectl --context "$profile" apply --server-side --namespace argocd \
    -f "https://raw.githubusercontent.com/argoproj/argo-cd/$argocd_version/manifests/install.yaml"
kubectl --context "$profile" --namespace argocd wait \
    --for=condition=Available deployment --all --timeout=300s
kubectl --context "$profile" --namespace argocd rollout status \
    statefulset/argocd-application-controller --timeout=300s
kubectl --context "$profile" apply -f "$hw_dir/bootstrap/namespaces.yaml"
kubectl --context "$profile" apply -f "$hw_dir/argocd/project.yaml"
kubectl --context "$profile" apply -f "$hw_dir/argocd/helm-repository.yaml"
printf 'Argo CD %s is ready in minikube profile %s. Apply dev/prod Applications after publishing the first chart.\n' \
    "$argocd_version" "$profile"
