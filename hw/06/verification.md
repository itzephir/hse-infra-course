# Проверка доставки hw6

Текущая схема проверена на работающем стенде: dev получает OCI chart, prod — готовые манифесты из main с выбранным digest. PreSync и динамические prod-теги из прежнего этапа больше не используются. Описание архитектуры — в [решении](solution.md).

[Решение](solution.md) · [Условие](README.md)

## Выбор prod-артефакта и границы проектов

- Для prod выбран образ успешной main-сборки [44092876883](https://github.com/itzephir/hse-infra-course/actions/runs/44092876883), source SHA `07f4867c0a0795d198c5826ed9a4512c01f4d853`, digest `sha256:e60e5a4c3efafb7b7b773c66ebe53461d94789654b8a8ab88ad806d92c14db24`.
- `prepare-prod-release.py` проверил метаданные этой сборки и сверил source SHA с artifact, подготовив локальные манифесты для review.
- Отдельно проверено отклонение run рабочей ветки: команда завершилась с ошибкой, оба prod-файла остались неизменными.
- `kubectl kustomize` рендерит только Deployment/Service в `hw6-relay-prod`, с указанным digest и source SHA. Helm dev проходит `helm lint --strict`.
- На работающем Argo CD проверены два запрета: dev-проект отклонил Application с назначением в prod namespace; prod-проект отклонил OCI Helm-источник. Оба получили `InvalidSpecError`, синхронизации не запускались, проверочные Applications удалены.
- Защита main остаётся предпосылкой учебной модели. Namespace-политики, квоты и сетевое усиление описаны как возможный следующий уровень, без изменения minikube.

## Проверка независимости prod от новой публикации CI

После принятия [PR №4](https://github.com/itzephir/hse-infra-course/pull/4) main разрешился в commit `eb080a066733e6a2dd0651c02c4f3a06e2779afb`. [Main workflow 44099698982](https://github.com/itzephir/hse-infra-course/actions/runs/44099698982) завершился успешно и выпустил:

```text
SOURCE_SHA=eb080a066733e6a2dd0651c02c4f3a06e2779afb
IMAGE=ghcr.io/itzephir/hse-infra-course@sha256:e62db4460c56ec8762cdbc493d3821e4ec6f25d82ed552b07ac6f14d07553d3f
CHART_VERSION=0.44099698982.1
```

- Dev без ручного refresh выбрал chart `0.44099698982.1` и новый digest `e62db446…`; `/version.json` вернул source SHA `eb080a0…`.
- Prod автоматически применил Kustomize-конфигурацию из нового main, но сохранил выбранный digest `e60e5a4c…` и source SHA `07f4867…`. Новая публикация CI не выбрала за него другой образ.
- Оба Application достигли `Synced / Healthy`; обе реплики prod готовы. `/healthz` dev и prod вернул `relay`, `/version.json` prod — полный выбранный source SHA `07f4867c0a0795d198c5826ed9a4512c01f4d853`.
- Оба Application используют отдельные AppProject. Прежний общий проект `relay-hw6` удалён после переключения.

## Предыдущий этап Helm-доставки

## Публикация из рабочей ветки

[Успешный workflow](https://github.com/itzephir/hse-infra-course/actions/runs/44090004399) для source commit `71fdff4e42edd0dfdbdb2236ddcc6652c45d0f56`:

- Образ: `ghcr.io/itzephir/hse-infra-course@sha256:ef024e401cb956b1da47bbce6f1857f91cecada948abade4255385bb6930fda1`.
- Chart: `oci://ghcr.io/itzephir/charts/relay`, версия `0.44090004399.1`.
- Chart скачан анонимно через `helm pull`; OCI digest chart — `sha256:c86072df45699236afad38bd0c2ef1495115670eca3d3532d81ed0509a90c2ce`.
- Dev Application с `targetRevision: '*'` выбрал эту версию. Deployment получил точный image digest и annotation `relay/source-revision` с указанным source SHA; rollout завершился.

PR-проверка [Actions](https://github.com/itzephir/hse-infra-course/actions/runs/44090401497) также прошла и не публиковала артефакты.

## Доставка из main

После merge [PR №2](https://github.com/itzephir/hse-infra-course/pull/2) source commit — `ede9180efb83db63a73bbc4daea5aa77b622ec69`.

[Workflow main](https://github.com/itzephir/hse-infra-course/actions/runs/44090921538) опубликовал:

```text
IMAGE=ghcr.io/itzephir/hse-infra-course@sha256:cafb574358c700493fffad0bbfd7553a29a7f8436adcd2018d63928fbe050194
CHART=oci://ghcr.io/itzephir/charts/relay
CHART_VERSION=0.44090921538.1
```

Dev получил chart этой версии. Prod имеет `targetRevision: main`, `path: hw/06/chart`; параметр `image.tag=sha-$ARGOCD_APP_REVISION` разрешился в `sha-ede9180efb83db63a73bbc4daea5aa77b622ec69`.

Проверен реальный PreSync Job: его `EXPECTED_REVISION` содержал SHA main, он ожидал эту версию через HTTP dev. Пока Job работал, прежние две реплики prod оставались Ready. После готовности dev prod выполнил rollout. Оба Application достигли `Synced / Healthy`.

Сверены фактические `containerStatuses[].imageID`: Pod dev и оба Pod prod использовали одинаковый digest `sha256:cafb574358c700493fffad0bbfd7553a29a7f8436adcd2018d63928fbe050194`.

## Опрос Helm registry

Во время миграции обнаружен старый кэш списка Helm-версий. Для этого небольшого стенда [refresh-settings.yaml](argocd/refresh-settings.yaml) задаёт опрос 30 секунд с jitter до 5 секунд и repo/default cache repo-server 60 секунд. Существующий кэш при переходе однократно сброшен через Hard Refresh; обычная доставка использует автоматический опрос.

Стенд использует minikube `hw6`, Kubernetes `v1.37.0`, Argo CD `v3.6.1`. Родительского Application и записи в GitOps-ветку в текущем процессе нет. CI не получает kubeconfig; публичный OCI chart читается без registry-пароля.

## Проверки артефактов

- Контейнерные HTTP smoke-тесты AMD64/ARM64 в CI: `/`, `/style.css`, `/mark.svg`, `/healthz`, точный source SHA в `/version.json`.
- `helm lint --strict`, рендеринг dev/prod и упаковка chart с точным digest. PreSync Job появляется только для prod и работает без ServiceAccount token.
- Семантическая версия chart `0.<GitHub run ID>.<attempt>` успешно упакована, опубликована и разрешена Argo CD.
- YAML, shell-синтаксис, ссылки документов и workflow проверены. Локальный actionlint старше настройки `concurrency.queue`; эту настройку дополнительно проверил реальный запуск GitHub Actions.

## Доступ

Пока работает [port-forward.sh](scripts/port-forward.sh): [dev](http://127.0.0.1:18080), [prod](http://127.0.0.1:18081), [Argo CD](https://127.0.0.1:18443).

Если локальные адреса перестали отвечать, повторно запустить `bash hw/06/scripts/port-forward.sh`. Начальный пароль Argo CD и команды остановки/возобновления minikube описаны в [решении](solution.md#запуск-и-доступ). Пароли и kubeconfig в Git не добавлены.
