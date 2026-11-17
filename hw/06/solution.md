# Домашнее задание №6. Доставка лендинга Relay

[Условие](README.md) · [К содержанию курса](../../README.md)

Стенд запущен и проверен: [CI, digest образа и результаты доставки dev → prod](verification.md).

## Приложение и общая схема

Для задания создано самостоятельное приложение **Relay** — небольшой абстрактный лендинг в [app/](app/). Он состоит из HTML, CSS и SVG, не требует базы данных, внешних сервисов или установки пакетов. Dockerfile упаковывает страницу в nginx без root-прав. Nginx слушает порт `8080`, `/healthz` возвращает `relay`, а `/version.json` содержит SHA исходного коммита, переданный при сборке.

Весь пример находится в одном репозитории [itzephir/hse-infra-course](https://github.com/itzephir/hse-infra-course). Контейнер публикуется в **`ghcr.io/itzephir/hse-infra-course`**. Локальный стенд — отдельный профиль minikube `hw6` с Argo CD. Любой push в исходную ветку обновляет dev, а push в `main` также обновляет prod после готовности dev. Команды для него явно выбирают `--context hw6`.

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

- Любой push в любую исходную ветку запускает сборку и публикацию, в том числе при изменении только документации. Исключена служебная ветка `gitops/hw6`, в которой бот хранит желаемое состояние доставки.
- Pull request с такими изменениями запускает сборку AMD64 и HTTP-проверки без публикации. Также предусмотрены ручной запуск и вызов как reusable workflow.
- Для push и ручного запуска Buildx/QEMU собирают `linux/amd64` и `linux/arm64` в один OCI index и публикуют `ghcr.io/itzephir/hse-infra-course:sha-S`, где S — полный SHA исходного коммита. ARM64 нужен для локального minikube на Apple Silicon.
- После публикации [smoke-image.sh](scripts/smoke-image.sh) запускает обе платформы по полученному digest. Он проверяет главную страницу, CSS, SVG, `/healthz` и точный SHA в `/version.json`. Успешный artifact `release.env` создаётся только после этих проверок.
- Artifact и сводка запуска содержат `SOURCE_SHA=S` и `IMAGE=ghcr.io/itzephir/hse-infra-course@sha256:D`. Для push CD полный IMAGE также возвращается как output workflow.

Для публикации используется `GITHUB_TOKEN` с `packages: write`, без отдельного registry-пароля. GHCR-пакет должен разрешать запись из этого репозитория. Для скачивания kubelet предполагается публичный пакет; приватный пакет требует заранее созданного `imagePullSecret` в каждом namespace. [GitHub: публикация образов](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [GHCR и доступ](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [Docker: несколько платформ](https://docs.docker.com/build/ci/github-actions/multi-platform/).

Тег связывает образ с исходниками, а **digest** фиксирует конкретную сборку. Продвижение между окружениями не пересобирает приложение: dev и prod получают один и тот же OCI index. В работающий Pod Kubernetes выбирает подходящий для узла платформенный образ из этого index.

## 1. Pull-модель: автоматическая доставка через Argo CD

Исходный код и манифесты находятся в обычных ветках репозитория. Отдельная служебная ветка **`gitops/hw6`** содержит только выбранные версии окружений:

```text
gitops/hw6
├── applications/
│   ├── dev.yaml    Application dev: точный source SHA и image digest
│   └── prod.yaml   Application prod: точный source SHA и image digest
└── .releases/
    ├── dev.json    Ветка-источник, SHA, digest, ссылка на Actions
    └── prod.json
```

После успешной сборки job `record-dev` вызывает [hw6-record-release.yml](../../.github/workflows/hw6-record-release.yml). Он получает source SHA и digest из build, обновляет `applications/dev.yaml` в служебной ветке и делает commit через `GITHUB_TOKEN` с правом `contents: write`. Job `record-prod` выполняется только при `github.ref == 'refs/heads/main'` и записывает **тот же digest** в prod. Исходные ветки бот не меняет.

Сборки и записи релиза используют общую очередь workflow (`concurrency`, `queue: max`) для всех исходных веток. Служебная ветка исключена из push-триггера. Кроме того, push через `GITHUB_TOKEN` не создаёт рекурсивный запуск Actions. PR выполняет сборку и проверки без доставки. [Очередь Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency), [события от GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token).

### Кто применяет манифесты

Родительский [Application relay-hw6-delivery](argocd/root.yaml) следит за `gitops/hw6`, каталогом `applications`. Он управляет двумя дочерними Application, которые получают Kubernetes-манифесты из **точного исходного commit SHA**, а не из подвижного имени ветки:

```yaml
spec:
  project: relay-hw6
  source:
    repoURL: https://github.com/itzephir/hse-infra-course.git
    targetRevision: SOURCE_COMMIT_SHA
    path: hw/06/manifests/overlays/dev
    kustomize:
      images:
        - relay=ghcr.io/itzephir/hse-infra-course@sha256:IMAGE_DIGEST
  destination:
    server: https://kubernetes.default.svc
    namespace: hw6-relay-dev
```

В реальном сгенерированном файле стоят полный SHA и полный digest. Kustomize override заменяет версию из исходного overlay. [publish-gitops.py](scripts/publish-gitops.py) проверяет совпадение source checkout с выбранным SHA и меняет только одно окружение. Шаблоны дочерних Application: [dev.yaml](argocd/dev.yaml), [prod.yaml](argocd/prod.yaml).

У dev стоит sync wave `0`, у prod — `1`. Родитель сначала применяет dev Application и ждёт его готовности, затем применяет новую prod Application. Для этого [application-health.yaml](argocd/application-health.yaml) восстанавливает оценку здоровья дочернего Application и проверяет **Synced + нужный source SHA + выбранный image override + Healthy**. Старый Healthy от предыдущей версии не открывает следующую волну. [Sync waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/), [настройка health checks](https://argo-cd.readthedocs.io/en/stable/operator-manual/health/).

```text
Push в feature → build/test → GHCR digest D
  → GitOps: dev = (source SHA, D)
  → Argo CD → dev

Push в main → build/test → GHCR digest D
  → GitOps: dev = (source SHA, D), prod = (тот же SHA, тот же D)
  → Argo CD wave 0: dev → Synced/Healthy для выбранной версии
  → Argo CD wave 1: prod
```

Общий dev используется всеми ветками: следующая принятая версия заменяет предыдущую. Argo CD согласует последнее желаемое состояние, поэтому при нескольких быстрых изменениях Git промежуточные версии могут быть пропущены. Если нужны отдельные preview для каждой ветки или обязательная проверка каждого промежуточного релиза, потребуется отдельный процесс продвижения. Для этого небольшого стенда выбран общий dev и prod только из main.

Argo CD опрашивает Git (стандартно 120 секунд плюс jitter до 60 секунд); webhook может ускорить обнаружение. Автосинхронизация, self-heal и prune включены у родителя и дочерних приложений. Workflow завершает запись желаемого состояния; реальную готовность доставки показывает Argo CD. CI не получает kubeconfig и не обращается к Kubernetes API. [Автоматическая синхронизация](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/).

[Проект приложения](argocd/project.yaml) разрешает только Deployment/Service в dev/prod. Отдельный [проект доставки](argocd/root-project.yaml) разрешает родителю только Application в namespace argocd. Оператор заранее создаёт namespaces. Откат выполняется новым commit в GitOps-ветке, возвращающим прежнюю пару source SHA и digest.

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
| Как выбирается dev-версия | Actions записывает source SHA и digest D в GitOps Application dev | Output сборки передаётся в dev job |
| Кто начинает применение | Контроллер замечает Git-изменение | Dev job вызывает kubectl |
| Как версия попадает в prod | Push в main выбирает тот же D; Argo CD применяет prod после волны dev | Успешный dev и environment approval; тот же output D |
| Что остаётся в истории | Git + artifact/запуск сборки | Запуск, параметры и artifact; их нужно сохранять |

В обеих моделях прослеживается цепочка **исходный commit S → успешная сборка → digest D → проверка dev → prod**. Сборка между окружениями не повторяется. Даже если тег `sha-S` позже перезапишут при повторной сборке, уже выбранный digest останется определённым содержимым.

## 4. Сравнение и выбор

| Критерий | Pull / Argo CD | Push / Actions |
| --- | --- | --- |
| Начальная настройка | Нужны контроллер, CRD и Application | Достаточно CI и kubectl при доступном API |
| Права CI | Registry; доступ к Kubernetes API не нужен | Credentials и сетевой доступ к кластеру |
| Ручной drift | Исправляется при self-heal | Остаётся до следующего применения |
| Выбор версии окружения | Source SHA и digest записаны в GitOps-ветке | В output и параметрах запуска |
| Dev → prod | Запись из main и волны синхронизации Argo CD | Зависимости jobs и environment approval |
| Удаление ресурсов | Prune удаляет управляемые объекты, исчезнувшие из Git | Обычный apply не удаляет исчезнувшие из YAML объекты |
| Откат | Возврат digest через Git | Повторное применение сохранённого релиза |
| Недоступность доставки | Новые изменения не согласуются; работающий сайт продолжает работать | Новая выкладка ждёт Actions или доступ к API |

**Для этого Kubernetes-стенда выбираю GitHub Actions + GHCR + Argo CD.** CI собирает сайт, а локальный контроллер сам забирает конфигурацию. Не нужно открывать Kubernetes API Mac для GitHub-hosted runner. Выбор source SHA и digest dev/prod виден в GitOps-ветке, и Argo CD исправляет drift. Минус — ради небольшого лендинга нужно обслуживать дополнительные компоненты; здесь это оправдано учебной задачей.

## Запуск и доступ

Предварительные условия: работающий Docker Desktop, minikube, kubectl и доступ к GitHub/GHCR. Версии стенда закреплены в [start-cluster.sh](scripts/start-cluster.sh): Kubernetes `v1.37.0`, Argo CD `v3.6.1`. Установка Argo CD использует официальный manifest выбранного релиза. [Minikube с Docker](https://minikube.sigs.k8s.io/docs/drivers/docker/), [установка Argo CD](https://argo-cd.readthedocs.io/en/stable/getting_started/).

```bash
bash hw/06/scripts/start-cluster.sh
# После создания служебной ветки gitops/hw6:
kubectl --context hw6 apply -f hw/06/argocd/root.yaml
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
