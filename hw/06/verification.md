# Проверка доставки hw6

[Решение](solution.md) · [Условие](README.md) · [Запуски CI](https://github.com/itzephir/hse-infra-course/actions/workflows/hw6-image.yml)

Стенд использует minikube `hw6`, Kubernetes `v1.37.0` и Argo CD `v3.6.1`. Dev получает OCI Helm chart, prod — манифесты из main с digest успешной main-сборки.

## События доставки

| Событие | Публикация CI | Действие Argo CD |
| --- | --- | --- |
| Открытие, новый commit или повторное открытие PR из ветки репозитория | Проверенный образ и Helm chart `relay` версии `0.<run ID>.<attempt>` | Общий dev выбирает последнюю версию chart |
| Push в main | Проверенный образ; отдельный job коммитит его digest и source SHA в prod-манифесты main | Prod получает служебный commit и обновляет Deployment |
| Push в другую ветку без PR | Выкладка не запускается | Состояние приложений сохраняется |
| PR из fork | Локальная AMD64-сборка и проверки без публикации | Автоматическая выкладка не настроена |

CI не получает kubeconfig или токен Argo CD. Build-задача имеет `contents: read` и `packages: write`; запись в Git разрешена отдельной задаче `promote-prod`, зависящей от успешной main-сборки. Служебный push через `GITHUB_TOKEN` не создаёт следующий push workflow.

## Проверки артефактов и конфигурации

- HTTP smoke-тесты AMD64/ARM64: `/`, `/style.css`, `/mark.svg`, `/healthz`, точный source SHA в `/version.json`.
- `helm lint --strict`, рендеринг dev chart и prod Kustomize overlay. Образ публикуется по неизменяемому digest, dev chart выпускается после проверок.
- `set-prod-release.py` проверен во временной копии: обновление digest и source SHA отражается в итоговом Deployment; неверный source SHA, другой registry repository или некорректный номер запуска отклоняются без изменения prod-файлов.
- Workflow проверен actionlint; локальная версия линтера не поддерживает `concurrency.queue`, поэтому эта строка проверяется исполнением GitHub Actions.
- Git diff не содержит ошибок пробелов. Main-задача коммитит только `kustomization.yaml` и `release.yaml` prod overlay; устаревшая main-сборка пропускает продвижение, git push выполняется без force.
- На работающем Argo CD проверены запреты AppProject: dev-проект отклонил назначение в prod namespace; prod-проект отклонил OCI Helm-источник. Проверочные Applications получили `InvalidSpecError` без запуска синхронизации и были удалены.

## Контроль автоматической доставки

[PR workflow 44131640640](https://github.com/itzephir/hse-infra-course/actions/runs/44131640640) успешно опубликовал образ и chart `0.44131640640.1` для source SHA `d3345b0187f8d83c5929eccdcffd9d13e0545ba9`. Argo CD автоматически выбрал этот chart для dev. Задача `promote-prod` получила статус `skipped`, prod сохранил свой main-образ.

1. Открыть PR, дождаться успешного workflow и выбора его chart в dev. Изменить любой файл в PR и проверить новый запуск и новую версию chart. Prod должен сохранить свой main-образ.
2. Принять PR в main. Дождаться задач `build` и `promote-prod`, затем служебного commit от `github-actions[bot]`, содержащего digest, source SHA и ссылку на этот main run.
3. Проверить, что служебный commit не запустил повторную сборку, а prod Application разрешил main в этот commit и достиг `Synced / Healthy`.
4. Сверить HTTP-версию prod с `SOURCE_SHA` main-сборки, а фактический образ Deployment — с `IMAGE` из её artifact `release.env`.

```bash
kubectl --context hw6 -n argocd get applications
kubectl --context hw6 -n hw6-relay-dev rollout status deployment/relay
kubectl --context hw6 -n hw6-relay-prod rollout status deployment/relay
kubectl --context hw6 -n hw6-relay-prod get deployment relay \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
curl -fsS http://127.0.0.1:18080/version.json
curl -fsS http://127.0.0.1:18081/version.json
```

Для автоматического обнаружения версий [refresh-settings.yaml](argocd/refresh-settings.yaml) задаёт опрос 30 секунд с jitter до 5 секунд и кэш repo-server 60 секунд.

## Доступ

Пока работает [port-forward.sh](scripts/port-forward.sh): [dev](http://127.0.0.1:18080), [prod](http://127.0.0.1:18081), [Argo CD](https://127.0.0.1:18443).

После rollout Pods локальные подключения при необходимости восстановить командой `bash hw/06/scripts/port-forward.sh`. Начальный пароль Argo CD и команды остановки/возобновления minikube описаны в [решении](solution.md#запуск-и-доступ). Пароли и kubeconfig в Git не добавлены.

Защита main считается условием учебной модели. Дополнительные namespace-политики, квоты и сетевое усиление minikube описаны в решении.
