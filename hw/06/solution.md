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

- Любой push в любую исходную ветку запускает сборку и публикацию, в том числе при изменении только документации. CI публикует проверенный образ и версионированный Helm chart в GHCR; запись в отдельную GitOps-ветку больше не нужна.
- Pull request с такими изменениями запускает сборку AMD64 и HTTP-проверки без публикации. Также предусмотрены ручной запуск и вызов как reusable workflow.
- Для push и ручного запуска Buildx/QEMU собирают `linux/amd64` и `linux/arm64` в один OCI index и публикуют кандидат с тегом `ci-R-A`, где R — номер запуска GitHub, A — номер попытки. После успешных HTTP- и Helm-проверок тот же digest получает тег `sha-S`, где S — полный SHA исходного коммита. ARM64 нужен для локального minikube на Apple Silicon.
- После публикации [smoke-image.sh](scripts/smoke-image.sh) запускает обе платформы по полученному digest. Он проверяет главную страницу, CSS, SVG, `/healthz` и точный SHA в `/version.json`. Успешный artifact `release.env` создаётся только после этих проверок.
- Artifact и сводка запуска содержат `SOURCE_SHA=S` и `IMAGE=ghcr.io/itzephir/hse-infra-course@sha256:D`. В artifact дополнительно сохраняются адрес chart и `CHART_VERSION`; для push CD полный IMAGE также возвращается как output workflow.

Для публикации используется `GITHUB_TOKEN` с `packages: write`, без отдельного registry-пароля. GHCR-пакет должен разрешать запись из этого репозитория. Для скачивания kubelet предполагается публичный пакет; приватный пакет требует заранее созданного `imagePullSecret` в каждом namespace. [GitHub: публикация образов](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [GHCR и доступ](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [Docker: несколько платформ](https://docs.docker.com/build/ci/github-actions/multi-platform/).

Тег связывает образ с исходниками, а **digest** фиксирует конкретную сборку. Продвижение между окружениями не пересобирает приложение: dev и prod получают один и тот же OCI index. В работающий Pod Kubernetes выбирает подходящий для узла платформенный образ из этого index.

## 1. Pull-модель: dev из Helm registry, prod из main

В [hw/06/chart](chart/) находится Helm chart `relay`: Deployment, Service и условный PreSync Job для prod. Базовые values задают одну реплику, настройки ресурсов и ссылку на образ. Шаблоны сохраняют nginx без root, файловую систему только для чтения и временный `/tmp`.

После сборки и проверок CI:

1. Публикует проверенный образ в `ghcr.io/itzephir/hse-infra-course` и тег `sha-S` для конкретного source commit S.
2. Создаёт копию chart, записывает в её values **точный image digest** и source SHA.
3. Упаковывает chart версией `0.R.A` (R — уникальный GitHub run ID, A — попытка) и публикует через `helm push` в **`oci://ghcr.io/itzephir/charts/relay`**.

Уникальная SemVer-версия позволяет Argo CD выбрать последнюю публикацию. Chart переносит описание ресурсов и ссылку на контейнер; сам контейнер хранится отдельным OCI-образом. Helm chart публикуется только после успешных проверок. [Helm OCI registries](https://docs.helm.sh/docs/v3/topics/registries/).

### Dev: последняя версия chart

[Application dev](argocd/dev.yaml):

```yaml
source:
  repoURL: ghcr.io/itzephir/charts
  chart: relay
  targetRevision: '*'
  helm:
    releaseName: relay
```

Здесь `targetRevision` — **диапазон версий chart**, а не Git commit. `*` выбирает максимальную доступную стабильную SemVer-версию. Любая ветка публикует новую версию chart, поэтому общий dev обновляется после любого успешного push. В опубликованном chart уже зафиксирован digest образа; Argo CD получает chart, выполняет `helm template` и применяет результат. `helm install` из CI не вызывается, жизненным циклом ресурсов управляет Argo CD. [Версии chart в Argo CD](https://argo-cd.readthedocs.io/en/stable/user-guide/tracking_strategies/), [интеграция Helm](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/).

В [refresh-settings.yaml](argocd/refresh-settings.yaml) для учебного стенда задан опрос каждые 30 секунд с jitter до 5 секунд и кэш repo-server на 60 секунд. Это позволяет обнаруживать новые версии OCI chart без ручного Hard Refresh. Настройки применяются до создания Applications; после изменения параметров repo-server нужен перезапуск соответствующего компонента. При миграции существующий длительный кэш был сброшен однократно, затем отдельно проверяется автоматическое обнаружение следующей публикации. [Настройки кэша Argo CD](https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd-cmd-params-cm-yaml/).

Для публичного OCI-источника [helm-repository.yaml](argocd/helm-repository.yaml) содержит только URL, тип `helm` и `enableOCI: true`; паролей в этом файле нет. Приватный chart требует отдельно настроенных registry credentials.

### Prod: chart прямо из main

[Application prod](argocd/prod.yaml):

```yaml
source:
  repoURL: https://github.com/itzephir/hse-infra-course.git
  targetRevision: main
  path: hw/06/chart
  helm:
    releaseName: relay
    valuesObject:
      replicaCount: 2
      promotion:
        enabled: true
    parameters:
      - name: image.tag
        value: sha-$ARGOCD_APP_REVISION
        forceString: true
      - name: sourceRevision
        value: $ARGOCD_APP_REVISION
        forceString: true
```

Prod постоянно следит за Git-веткой `main`. Argo CD подставляет SHA прочитанного коммита в `$ARGOCD_APP_REVISION`: из main S получится image `ghcr.io/itzephir/hse-infra-course:sha-S`. Значения вычисляются при рендеринге, в Application не требуется записывать новый commit SHA после каждого push. [Переменные среды рендеринга](https://argo-cd.readthedocs.io/en/stable/user-guide/build-environment/).

PreSync Job из chart проверяет HTTP `/version.json` в dev и ждёт **этот source SHA**. Пока версия main не появилась в готовом dev, prod Deployment не изменяется. Тег `sha-S` публикуется только после проверок CI и указывает на тот же образ, digest которого записан в dev chart. После успешного Job Argo CD выкладывает prod. Job работает без Kubernetes API, токена ServiceAccount и прав на изменение ресурсов; его действие — чтение HTTP внутри кластера.

```text
Push в любую ветку → image build/test → GHCR image
  → Helm package с digest → GHCR chart → Argo CD → dev

Push в main → та же цепочка публикации → dev
  + Argo CD читает chart из main S
  → PreSync: дождаться S в dev → prod: image sha-S
```

При ошибке CI или отсутствии нужной версии в dev проверка prod завершается неуспешно, а прежний prod Deployment остаётся работать. Для transient ошибок настроены повторы синхронизации. Последующий push другой ветки обновляет общий dev и оставляет prod на main. Если новые chart выходят быстрее опроса, промежуточные версии могут быть пропущены; PreSync в этом случае не разрешит выкладку main, который не успел пройти dev. Для обязательной проверки каждого релиза нужны отдельные dev-окружения либо очередь продвижения.

Argo CD автоматически проверяет источники и синхронизирует изменения; `selfHeal` исправляет drift, `prune` удаляет управляемые ресурсы, исчезнувшие из chart. CI имеет только доступ к GHCR и не получает kubeconfig. Прежние родительское приложение и запись Application в `gitops/hw6` больше не используются. [Проект](argocd/project.yaml) разрешает Git/OCI-источники, два namespaces и Deployment/Service/Job.

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
| Как выбирается dev-версия | CI публикует chart с digest D; dev выбирает последнюю версию chart | Output сборки передаётся в dev job |
| Кто начинает применение | Контроллер замечает новую версию chart | Dev job вызывает kubectl |
| Как версия попадает в prod | Prod читает chart из main; PreSync ждёт этот source SHA в dev, image sha-S указывает на D | Успешный dev и environment approval; тот же output D |
| Что остаётся в истории | Git + artifact/запуск сборки | Запуск, параметры и artifact; их нужно сохранять |

В обеих моделях прослеживается цепочка **исходный commit S → успешная сборка → digest D → проверка dev → prod**. Сборка между окружениями не повторяется. Даже если тег `sha-S` позже перезапишут при повторной сборке, уже выбранный digest останется определённым содержимым.

## 4. Сравнение и выбор

| Критерий | Pull / Argo CD | Push / Actions |
| --- | --- | --- |
| Начальная настройка | Нужны контроллер, CRD и Application | Достаточно CI и kubectl при доступном API |
| Права CI | Registry; доступ к Kubernetes API не нужен | Credentials и сетевой доступ к кластеру |
| Ручной drift | Исправляется при self-heal | Остаётся до следующего применения |
| Выбор версии окружения | Dev: версия OCI chart и digest; prod: main и тег sha-S | В output и параметрах запуска |
| Dev → prod | PreSync-проверка main SHA в dev | Зависимости jobs и environment approval |
| Удаление ресурсов | Prune удаляет управляемые объекты, исчезнувшие из Git | Обычный apply не удаляет исчезнувшие из YAML объекты |
| Откат | Выбор прежнего chart dev; revert в main для prod | Повторное применение сохранённого релиза |
| Недоступность доставки | Новые изменения не согласуются; работающий сайт продолжает работать | Новая выкладка ждёт Actions или доступ к API |

**Для этого Kubernetes-стенда выбираю GitHub Actions + GHCR + Argo CD.** CI собирает сайт, а локальный контроллер сам забирает конфигурацию. Не нужно открывать Kubernetes API Mac для GitHub-hosted runner. Версии dev видны в Helm registry и CI artifacts, prod следует main, а Argo CD исправляет drift. Минус — ради небольшого лендинга нужно обслуживать дополнительные компоненты; здесь это оправдано учебной задачей.

## Запуск и доступ

Предварительные условия: работающий Docker Desktop, minikube, kubectl и доступ к GitHub/GHCR. Версии стенда закреплены в [start-cluster.sh](scripts/start-cluster.sh): Kubernetes `v1.37.0`, Argo CD `v3.6.1`. Установка Argo CD использует официальный manifest выбранного релиза. [Minikube с Docker](https://minikube.sigs.k8s.io/docs/drivers/docker/), [установка Argo CD](https://argo-cd.readthedocs.io/en/stable/getting_started/).

```bash
bash hw/06/scripts/start-cluster.sh
# После первой публикации chart и наличия chart в main:
kubectl --context hw6 apply -f hw/06/argocd/dev.yaml
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
