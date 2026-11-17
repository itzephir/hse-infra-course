# Домашнее задание №6. Доставка лендинга Relay

[Условие](README.md) · [К содержанию курса](../../README.md)

Стенд запущен и проверен: [CI, digest образа и результаты доставки dev → prod](verification.md).

## Приложение и общая схема

Для задания создано самостоятельное приложение **Relay** — небольшой абстрактный лендинг в [app/](app/). Он состоит из HTML, CSS и SVG, не требует базы данных, внешних сервисов или установки пакетов. Dockerfile упаковывает страницу в nginx без root-прав. Nginx слушает порт `8080`, `/healthz` возвращает `relay`, а `/version.json` содержит SHA исходного коммита, переданный при сборке.

Весь пример находится в одном репозитории [itzephir/hse-infra-course](https://github.com/itzephir/hse-infra-course). Контейнер публикуется в **`ghcr.io/itzephir/hse-infra-course`**. Локальный стенд — отдельный профиль minikube `hw6` с Argo CD. Команды для него явно выбирают `--context hw6`.

| Параметр | dev | prod |
| --- | --- | --- |
| Namespace | `hw6-relay-dev` | `hw6-relay-prod` |
| Deployment / Service | `relay` | `relay` |
| Реплики | 1 | 2 |
| Kustomize overlay | `hw/06/manifests/overlays/dev` | `hw/06/manifests/overlays/prod` |
| Argo CD Application | `relay-hw6-dev` | `relay-hw6-prod` |
| Локальный адрес после port-forward | <http://127.0.0.1:18080> | <http://127.0.0.1:18081> |

Это два учебных окружения на одном узле. Две реплики prod показывают разницу конфигурации, но не защищают от отказа узла. Service имеет тип ClusterIP; локальный доступ организован через port-forward без публичного Ingress.

## Сборка в GitHub Actions и публикация в GHCR

Действующий workflow: [`.github/workflows/hw6-image.yml`](../../.github/workflows/hw6-image.yml).

- Push с изменениями `hw/06/app/**`, проверки контейнера или самого workflow запускает сборку и публикацию. Ветки не ограничены: учебную ветку можно проверить до merge.
- Pull request с такими изменениями запускает сборку AMD64 и HTTP-проверки без публикации. Также предусмотрены ручной запуск и вызов как reusable workflow.
- Для push и ручного запуска Buildx/QEMU собирают `linux/amd64` и `linux/arm64` в один OCI index и публикуют `ghcr.io/itzephir/hse-infra-course:sha-S`, где S — полный SHA исходного коммита. ARM64 нужен для локального minikube на Apple Silicon.
- После публикации [smoke-image.sh](scripts/smoke-image.sh) запускает обе платформы по полученному digest. Он проверяет главную страницу, CSS, SVG, `/healthz` и точный SHA в `/version.json`. Успешный artifact `release.env` создаётся только после этих проверок.
- Artifact и сводка запуска содержат `SOURCE_SHA=S` и `IMAGE=ghcr.io/itzephir/hse-infra-course@sha256:D`. Для push CD полный IMAGE также возвращается как output workflow.

Для публикации используется `GITHUB_TOKEN` с `packages: write`, без отдельного registry-пароля. GHCR-пакет должен разрешать запись из этого репозитория. Для скачивания kubelet предполагается публичный пакет; приватный пакет требует заранее созданного `imagePullSecret` в каждом namespace. [GitHub: публикация образов](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [GHCR и доступ](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [Docker: несколько платформ](https://docs.docker.com/build/ci/github-actions/multi-platform/).

Тег связывает образ с исходниками, а **digest** фиксирует конкретную сборку. Продвижение между окружениями не пересобирает приложение: dev и prod получают один и тот же OCI index. В работающий Pod Kubernetes выбирает подходящий для узла платформенный образ из этого index.

## 1. Pull-модель: Argo CD

### Структура Git

```text
.github/workflows/hw6-image.yml      Действующий CI с публикацией в GHCR
hw/06/
├── app/                            HTML, CSS, SVG, nginx.conf, Dockerfile
├── manifests/
│   ├── base/                       Deployment и Service
│   └── overlays/
│       ├── dev/kustomization.yaml  Namespace, 1 реплика, digest dev
│       └── prod/kustomization.yaml Namespace, 2 реплики, digest prod
├── argocd/
│   ├── project.yaml                Разрешённый источник и окружения
│   ├── dev.yaml                    Application dev
│   └── prod.yaml                   Application prod
├── bootstrap/namespaces.yaml
├── scripts/                        Запуск стенда, проверки и фиксация образа
├── workflows/                      Альтернативные примеры push CD
├── README.md
└── solution.md
```

Kustomize собирает общие Deployment/Service и добавляет параметры окружения. Контейнер имеет readiness `/`, liveness `/healthz`, requests/limits, файловую систему только для чтения и временный `emptyDir` в `/tmp`. Постоянные тома не нужны. [Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/).

### Application dev и prod

Полные файлы: [dev.yaml](argocd/dev.yaml), [prod.yaml](argocd/prod.yaml). Существенная часть dev:

```yaml
spec:
  project: relay-hw6
  source:
    repoURL: https://github.com/itzephir/hse-infra-course.git
    targetRevision: codex/hw6-gitops
    path: hw/06/manifests/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: hw6-relay-dev
  syncPolicy:
    automated:
      enabled: true
      prune: true
      selfHeal: true
      allowEmpty: false
```

В prod используются путь `hw/06/manifests/overlays/prod` и namespace `hw6-relay-prod`. Для воспроизводимой демонстрации оба Application читают опубликованную учебную ветку `codex/hw6-gitops`. После принятия работы можно переключить `targetRevision` на `main`; в обычной эксплуатации эту ветку следует защитить PR-проверками.

Argo CD находится внутри кластера. Он получает Git, запускает Kustomize для выбранного каталога, сравнивает результат с Kubernetes и применяет расхождения. Git опрашивается периодически: стандартный интервал — 120 секунд плюс jitter до 60 секунд; webhook позволяет обнаруживать изменения быстрее. `selfHeal` восстанавливает состояние после ручного изменения, `prune` удаляет управляемый объект, удалённый из Git. Сборочный CI не имеет доступа к Kubernetes API. [Auto-sync Argo CD](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/).

[AppProject](argocd/project.yaml) ограничивает источник этим репозиторием, назначения двумя namespaces, а типы ресурсов — Deployment и Service. Namespaces заранее создаёт оператор. AppProject дополняет Kubernetes RBAC контроллера. [Проекты Argo CD](https://argo-cd.readthedocs.io/en/stable/user-guide/projects/).

### Новый образ и продвижение dev → prod

```text
Commit S → Actions → GHCR:sha-S → проверенный digest D
  → commit/PR: dev image = D → Argo CD → dev
  → Synced + Healthy + проверка страницы и /version.json
  → commit/PR: prod image = тот же D → Argo CD → prod
```

После успешной сборки разработчик копирует полный `IMAGE` из artifact и выполняет:

```bash
python3 hw/06/scripts/pin-image.py dev "$IMAGE"
```

Это меняет только digest dev overlay. После публикации изменения Argo CD доставляет dev. Проверяются `Synced/Healthy`, ожидаемый digest в Deployment, HTTP-ответы и SHA исходников в `/version.json`. Проверка самого сайта в браузере дополняет статус Kubernetes.

Далее выполняется `pin-image.py prod "$IMAGE"` с **тем же сохранённым IMAGE**. Изменение prod публикуется отдельно, после проверки dev. При работе через защищённую основную ветку это два последовательных PR; в локальной демонстрации — два отдельных коммита учебной ветки. В описании promotion следует сохранить ссылку на сборку, digest и результат проверки dev. При появлении новой версии dev нельзя автоматически подменять этим значением уже выбранный релиз.

Сам Argo CD не связывает два Application зависимостью dev → prod: порядок здесь обеспечивает процесс продвижения. Для маленького лендинга двух изменений Git достаточно; отдельный image updater не нужен. Обновление тега в GHCR без изменения image в Git не запускает выкладку. Откат — новое изменение Git, возвращающее предыдущий проверенный digest.

## 2. Push-модель: GitHub Actions → kubectl apply

Альтернативные примеры сохранены в [hw6-push-cd.yml](workflows/hw6-push-cd.yml) и [hw6-deploy-push.yml](workflows/hw6-deploy-push.yml). Для запуска их нужно разместить в `.github/workflows/` рядом с действующим `hw6-image.yml`. В текущем стенде ресурсами управляет Argo CD; эти примеры на него не нацелены.

| Job | Триггер | Источник и действие |
| --- | --- | --- |
| `prepare` | Ручной `workflow_dispatch(source_sha, config_ref)` | Проверяет полный SHA S, разрешает ref манифестов в конкретный commit C |
| `build` | Успешный prepare | Вызывает `hw6-image.yml`, собирает S, возвращает проверенный IMAGE с digest D |
| `dev` | Успешный build | Checkout C, overlay dev, подстановка D, apply и проверки |
| `prod` | Успешный dev и разрешение environment | Checkout того же C, overlay prod, тот же D, apply и проверки |

```yaml
prod:
  needs: [prepare, build, dev]
  permissions:
    contents: read
  uses: ./.github/workflows/hw6-deploy-push.yml
  with:
    target: prod
    image: ${{ needs.build.outputs.image }}
    config_sha: ${{ needs.prepare.outputs.config_sha }}
  secrets: inherit
```

Вызываемая задача использует `environment: hw6-${{ inputs.target }}`. В настройках `hw6-prod` нужно включить required reviewer и разрешить ветку доставки: наличие поля environment само по себе не включает approval. Для личного проекта self-review должен быть разрешён либо потребуется другой reviewer. [GitHub Environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

[deploy-push.sh](scripts/deploy-push.sh) фиксирует образ во временной копии конфигурации и выполняет:

```bash
kubectl kustomize "$release_dir/manifests/overlays/$target" > "$release_dir/release.yaml"
kubectl apply --namespace "$namespace" -f "$release_dir/release.yaml"
kubectl rollout status --namespace "$namespace" deployment/relay --timeout=180s
```

После rollout проверяются ожидаемый image, `/healthz`, главная страница и `/version.json`. Ошибка dev блокирует prod. `needs.build.outputs.image` передаёт один digest, а `needs.prepare.outputs.config_sha` фиксирует одну ревизию конфигурации для обоих этапов. `concurrency` сериализует весь релиз, включая ожидание разрешения prod.

У environments разные secrets `KUBECONFIG`; их учётные записи ограничены собственным namespace и правами на Deployment/Service, чтение Pods/ReplicaSets и `pods/portforward`. Для push к локальному minikube обычный GitHub-hosted runner не имеет сетевого пути к API. Потребуется отдельно настроенный runner в доступной сети либо учебный внешний кластер. Передавать kubeconfig GitHub-hosted runner без решения вопроса связности недостаточно.

После завершения push workflow постоянного сравнения с Git нет. Для отката повторно применяется сохранённая конфигурация с прежним проверенным digest; автоматического rollback в примере нет. Одновременное управление этими же ресурсами через Argo CD и push pipeline вызовет конфликт состояния.

## 3. Как выбранная версия попадает в кластер

Kubernetes не следит за новыми тегами registry. Новый rollout начинается после изменения `Deployment.spec.template`, здесь — `containers[].image`.

| Вопрос | Pull / Argo CD | Push / Actions |
| --- | --- | --- |
| Кто собирает и где хранит | Actions → `ghcr.io/itzephir/hse-infra-course` | Тот же CI и GHCR |
| Как выбирается dev-версия | Digest D записывается в dev overlay через commit/PR | Output сборки передаётся в dev job |
| Кто начинает применение | Контроллер замечает Git-изменение | Dev job вызывает kubectl |
| Как версия попадает в prod | Отдельное изменение prod overlay с проверенным D | Успешный dev и environment approval; тот же output D |
| Что остаётся в истории | Git + artifact/запуск сборки | Запуск, параметры и artifact; их нужно сохранять |

В обеих моделях прослеживается цепочка **исходный commit S → успешная сборка → digest D → проверка dev → prod**. Сборка между окружениями не повторяется. Даже если тег `sha-S` позже перезапишут при повторной сборке, уже выбранный digest останется определённым содержимым.

## 4. Сравнение и выбор

| Критерий | Pull / Argo CD | Push / Actions |
| --- | --- | --- |
| Начальная настройка | Нужны контроллер, CRD и Application | Достаточно CI и kubectl при доступном API |
| Права CI | Registry; доступ к Kubernetes API не нужен | Credentials и сетевой доступ к кластеру |
| Ручной drift | Исправляется при self-heal | Остаётся до следующего применения |
| Выбор версии окружения | Явно записан в Git | В output и параметрах запуска |
| Dev → prod | Здесь порядок обеспечивает процесс promotion | Зависимости jobs и environment approval |
| Удаление ресурсов | Prune удаляет управляемые объекты, исчезнувшие из Git | Обычный apply не удаляет исчезнувшие из YAML объекты |
| Откат | Возврат digest через Git | Повторное применение сохранённого релиза |
| Недоступность доставки | Новые изменения не согласуются; работающий сайт продолжает работать | Новая выкладка ждёт Actions или доступ к API |

**Для этого Kubernetes-стенда выбираю GitHub Actions + GHCR + Argo CD.** CI собирает сайт, а локальный контроллер сам забирает конфигурацию. Не нужно открывать Kubernetes API Mac для GitHub-hosted runner. Выбор версии dev/prod виден в Git, и Argo CD исправляет drift. Минус — ради небольшого лендинга нужно обслуживать дополнительные компоненты; здесь это оправдано учебной задачей.

## Запуск и доступ

Предварительные условия: работающий Docker Desktop, minikube, kubectl и доступ к GitHub/GHCR. Версии стенда закреплены в [start-cluster.sh](scripts/start-cluster.sh): Kubernetes `v1.37.0`, Argo CD `v3.6.1`. Установка Argo CD использует официальный manifest выбранного релиза. [Minikube с Docker](https://minikube.sigs.k8s.io/docs/drivers/docker/), [установка Argo CD](https://argo-cd.readthedocs.io/en/stable/getting_started/).

```bash
bash hw/06/scripts/start-cluster.sh
# После публикации проверенных digest в overlays:
kubectl --context hw6 apply -f hw/06/argocd/dev.yaml
# После проверки dev и отдельного promotion:
kubectl --context hw6 apply -f hw/06/argocd/prod.yaml
bash hw/06/scripts/port-forward.sh
```

Лендинг dev: <http://127.0.0.1:18080>, prod: <http://127.0.0.1:18081>, Argo CD: <https://127.0.0.1:18443>. У Argo CD локальный самоподписанный сертификат. Логин — `admin`; начальный пароль получить локально, не сохраняя в Git:

```bash
kubectl --context hw6 -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 --decode
```

Проверка состояния и конкретной версии:

```bash
kubectl --context hw6 -n argocd get applications
kubectl --context hw6 -n hw6-relay-dev rollout status deployment/relay
kubectl --context hw6 -n hw6-relay-prod rollout status deployment/relay
curl -fsS http://127.0.0.1:18080/version.json
curl -fsS http://127.0.0.1:18081/version.json
```

Остановить учебный кластер: `minikube stop --profile hw6`. Возобновить: `minikube start --profile hw6 --keep-context`, затем снова запустить port-forward. Учётные данные и kubeconfig в репозиторий не включаются.
