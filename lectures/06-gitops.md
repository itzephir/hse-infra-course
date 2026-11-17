# Лекция 6. GitOps и Argo CD

[К содержанию курса](../README.md) · [Предыдущая лекция](05-kubernetes-storage.md)

Тема: декларативная доставка, непрерывное согласование, Argo CD и Flux. Дата на слайдах: 10.11.2026. Источник: `Л6.pdf`, 23 слайда; автор PDF - Максим Новосельцев. Учтены [исходные заметки с занятия](06-gitops-in-class.md).

Определения и связи изложены своими словами, номера слайдов указаны по разделам. YAML-примеры адаптированы; фрагменты конфигурации отмечены отдельно. Дополнительные уточнения сопровождаются ссылками на документацию. Команды не выполнялись на кластере; адреса репозиториев и токены в примерах условные.

## 1. Зачем нужен GitOps после успешного pipeline

Слайды 1-3.

Обычный pipeline может применить манифесты и успешно завершиться. Позднее кто-то вручную изменит число реплик или ConfigMap. Запущенный ранее pipeline уже не сравнивает кластер с Git, поэтому возникает **drift** - расхождение фактической конфигурации и принятого описания.

**GitOps** - подход, при котором желаемое состояние хранится в версионируемом декларативном виде, автоматически получается системой доставки и непрерывно согласуется с управляемой средой.

Четыре принципа из лекции:

1. Декларативное описание желаемого состояния.
2. Версии и история изменений.
3. Автоматическое получение конфигурации.
4. Непрерывное согласование с фактическим состоянием.

```text
Git -> получение исходников -> генерация манифестов
  -> сравнение с кластером -> применение по заданной политике
  -> повторное сравнение
```

Команда определяет, какие расхождения исправлять автоматически, а какие только показывать оператору. Само хранение YAML в Git ещё не создаёт непрерывное согласование.

## 2. Push и pull: кто доставляет изменения

Слайд 4; дополнено заметками с занятия.

| Вопрос | Push | Pull / GitOps |
| --- | --- | --- |
| Кто применяет конфигурацию | Pipeline или другая система доставки | Контроллер доставки |
| Где нужен доступ к Kubernetes API | У выполняющей доставку системы | У контроллера |
| Что происходит после применения | Зависит от дальнейшего процесса | Контроллер продолжает сравнение |
| Роль CI | Сборка и проверки | Сборка и проверки |

Типичная цепочка: CI собирает и проверяет образ, затем в конфигурации окружения фиксируют выбранную версию. Контроллер получает изменение и доставляет его в кластер.

Из заметок с занятия: если GitLab Runner имеет широкие права в кластере, возможность менять pipeline становится чувствительным доступом. Точный риск зависит от прав runner, учётной записи и правил изменения pipeline; полный доступ не возникает автоматически у любого CI.

В pull-модели CI можно оставить без прямого доступа к кластеру. При этом нужно контролировать права самого GitOps-контроллера и возможность менять репозиторий, из которого он получает конфигурацию.

## 3. Argo CD и Flux

Слайды 5-6.

| Критерий            | Argo CD                                      | Flux                                          |
| ------------------- | -------------------------------------------- | --------------------------------------------- |
| Единица описания    | `Application`                                | Несколько специализированных CRD              |
| Управление          | Собственные UI и CLI                         | Kubernetes-объекты и CLI                      |
| Helm                | Рендеринг chart; доставкой управляет Argo CD | Управление Helm releases через контроллер     |
| Ограничение доступа | Projects и RBAC Argo CD                      | Kubernetes-механизмы и настройки контроллеров |

Оба инструмента реализуют GitOps, но по-разному организуют управление.

Пример Flux разделяет получение источника и применение:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: webapp
  namespace: flux-system
spec:
  interval: 1m
  url: https://git.example.org/team/config.git
  ref:
    branch: main
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: webapp-dev
  namespace: flux-system
spec:
  interval: 5m
  path: ./apps/webapp/overlays/dev
  prune: true
  sourceRef:
    kind: GitRepository
    name: webapp
  targetNamespace: webapp-dev
```

`GitRepository` описывает источник и обновление его содержимого. Flux `Kustomization` выбирает каталог, ссылается на источник и задаёт применение результата. Целевой namespace должен быть подготовлен или создаваться управляемыми манифестами.

**Flux Kustomization и файл `kustomization.yaml` - разные сущности.** Первый является CRD контроллера Flux, второй - входным файлом инструмента Kustomize из [лекции 4](04-application-configuration.md).

## 4. Архитектура Argo CD

Слайд 7.

| Компонент | Задача |
| --- | --- |
| Repository Server | Получает исходники и генерирует итоговые манифесты |
| Application Controller | Сравнивает желаемое и фактическое состояние, выполняет синхронизацию |
| API Server Argo CD | Обслуживает UI и CLI, проверяет права пользователей |

API Server Argo CD и Kubernetes API Server - разные компоненты. Первый предоставляет интерфейс системы доставки; через второй выполняется управление объектами кластера.

Argo CD может управлять локальным кластером и подключёнными внешними кластерами в пределах выданных ему прав.

## 5. Application: источник, назначение и политика

Слайд 8.

**Application** связывает желаемую конфигурацию с местом её применения:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: webapp-dev
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://git.example.org/team/config.git
    targetRevision: main
    path: apps/webapp/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: webapp-dev
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
```

| Поле | Вопрос |
| --- | --- |
| `source` | Откуда получить конфигурацию и какую ревизию использовать? |
| `destination` | В какой кластер и namespace доставить? |
| `project` | Какие ограничения Argo CD действуют для приложения? |
| `syncPolicy` | Как выполнять синхронизацию? |

Сам объект Application расположен в `argocd`, а ресурсы приложения - в `webapp-dev`. `https://kubernetes.default.svc` в этом примере обозначает локальный кластер.

`CreateNamespace=true` разрешает создание целевого namespace при синхронизации, если позволяют права и ограничения проекта. Эта опция сама по себе не включает auto-sync.

## 6. Источники: Kustomize, Helm и несколько репозиториев

Слайды 9-11.

### Kustomize overlay

Если выбран `apps/webapp/overlays/dev`, Argo CD собирает именно этот overlay. Например, его `kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namespace: webapp-dev
replicas:
  - name: webapp
    count: 2
```

В кластер отправляется собранный результат, а не файл Kustomization как самостоятельный Kubernetes-ресурс.

### Helm chart из Git

Фрагмент внутри `Application.spec`:

```yaml
source:
  repoURL: https://git.example.org/team/config.git
  targetRevision: main
  path: charts/webapp
  helm:
    releaseName: webapp
    valueFiles:
      - values-prod.yaml
```

`path` указывает каталог chart, `valueFiles` - параметры окружения. `releaseName` задаёт имя, используемое при рендеринге шаблонов.

**В этой модели жизненный цикл ведёт Argo CD.** Использование Helm для рендеринга не создаёт обычную историю установок через `helm install` и `helm upgrade`. Управлять таким приложением как независимым Helm release было бы смешением двух владельцев доставки.

### Внешний chart и отдельный Git с values

Фрагмент `Application.spec`, использующий `sources` вместо `source`:

```yaml
sources:
  - repoURL: https://charts.example.org
    chart: webapp
    targetRevision: "1.4.0"
    helm:
      valueFiles:
        - $values/environments/prod/webapp.yaml
  - repoURL: https://git.example.org/team/config.git
    targetRevision: main
    ref: values
destination:
  server: https://kubernetes.default.svc
  namespace: webapp-prod
```

Первый источник предоставляет chart заданной версии. Второй предоставляет values: `ref: values` вводит ссылку `$values` на корень второго репозитория. Без `path` этот источник используется для файлов значений, а не для отдельной генерации ресурсов.

## 7. Auto-sync, self-heal и prune

Слайд 12.

Фрагмент `Application.spec`:

```yaml
syncPolicy:
  automated:
    enabled: true
    selfHeal: true
    prune: true
    allowEmpty: false
  syncOptions:
    - CreateNamespace=true
```

| Настройка | Назначение |
| --- | --- |
| `automated.enabled` | Включить автоматическую синхронизацию |
| `selfHeal` | Автоматически исправлять расхождения из-за изменений в кластере |
| `prune` | Удалять управляемые ресурсы, которые исчезли из желаемой конфигурации |
| `allowEmpty: false` | Сохранять защиту от автоматического удаления всех ресурсов при пустом результате генерации |
| `CreateNamespace=true` | Создавать namespace назначения при необходимости |

Примеры: новый commit меняет образ - работает auto-sync; ручное изменение Deployment расходится с Git - его может исправить self-heal; удалённый из Git Service может быть удалён из кластера через prune.

Prune относится к ресурсам приложения, а не ко всем объектам целевого namespace. Решения об автоматическом исправлении и удалении принимаются отдельно: включение auto-sync не означает автоматическое включение всех остальных настроек.

## 8. Sync Status и Health

Слайд 13.

**Sync Status** отвечает на вопрос о соответствии желаемой конфигурации. **Health** - о состоянии управляемых ресурсов.

| Сочетание | Как понимать |
| --- | --- |
| `OutOfSync / Healthy` | Ресурсы работоспособны, но конфигурация отличается от источника |
| `Synced / Progressing` | Конфигурация применена, ресурсы ещё достигают готовности |
| `Synced / Degraded` | Конфигурация совпадает, но ресурс неисправен |
| `Synced / Healthy` | Конфигурация согласована, ресурсы признаны здоровыми |

Статус заполняет контроллер; его не нужно задавать в исходном манифесте. Фрагмент ответа API:

```yaml
status:
  sync:
    status: Synced
    revision: "<commit-sha>"
  health:
    status: Healthy
```

Готовность ресурсов не заменяет проверку пользовательского сценария: сервис может отвечать с ошибкой даже при формально готовых Pod.

## 9. Параметры применения и повторы

Слайд 14.

Фрагмент `Application.spec`:

```yaml
syncPolicy:
  syncOptions:
    - ApplyOutOfSyncOnly=true
    - FailOnSharedResource=true
  retry:
    limit: 3
    backoff:
      duration: 5s
      factor: 2
      maxDuration: 1m
```

`ApplyOutOfSyncOnly=true` ограничивает применение отличающимися ресурсами. `FailOnSharedResource=true` останавливает синхронизацию, если обнаружен ресурс, уже управляемый другим Application. `retry` задаёт ограниченные повторные попытки с растущей задержкой; `maxDuration` ограничивает задержку между ними.

Уточнение к слайду: ручной **selective sync** выбранных ресурсов пропускает hooks. Его следует отличать от `ApplyOutOfSyncOnly=true`: в актуальной документации этой опции hooks сохраняются и операция записывается в историю. Для установленной версии нужно проверять соответствующую документацию. [Selective Sync](https://argo-cd.readthedocs.io/en/stable/user-guide/selective_sync/), [Apply Resources OutOfSync Only](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/#apply-resources-outofsync-only).

## 10. Исключения из сравнения и владельцы полей

Слайд 15.

Иногда отдельным полем управляет другой механизм. Например, число реплик меняет оператор или autoscaler, а остальные поля Deployment берутся из Git.

Фрагмент `Application.spec`:

```yaml
ignoreDifferences:
  - group: apps
    kind: Deployment
    name: webapp
    namespace: webapp-dev
    jsonPointers:
      - /spec/replicas
syncPolicy:
  syncOptions:
    - RespectIgnoreDifferences=true
```

`ignoreDifferences` исключает поле из вычисления diff. `RespectIgnoreDifferences=true` учитывает это исключение также при синхронизации уже существующего объекта. При первом создании, когда live-объекта ещё нет, применяется исходное описание. [Документация об исключениях при sync](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/#respect-ignore-differences-configs).

Важно заранее определить владельца поля. Иначе ручное масштабирование с двух до четырёх реплик будет постоянно конфликтовать с контроллером, возвращающим значение из Git.

## 11. Порядок применения: waves и hooks

Слайды 16-17.

**Sync wave** задаёт порядок ресурсов внутри фазы: меньшее число применяется раньше. Например, namespace в wave `-1`, ConfigMap в wave `0`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: webapp-dev
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: webapp-config
  namespace: webapp-dev
  annotations:
    argocd.argoproj.io/sync-wave: "0"
data:
  LOG_LEVEL: info
```

**Hook** - ресурс, выполняемый на определённой фазе операции. В лекции показан `PostSync`: проверка после успешной синхронизации и достижения ресурсами готовности.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  generateName: webapp-smoke-
  namespace: webapp-dev
  annotations:
    argocd.argoproj.io/hook: PostSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  backoffLimit: 1
  activeDeadlineSeconds: 120
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: check
          image: curlimages/curl:8.12.1
          args:
            - --fail
            - --max-time
            - "10"
            - http://webapp.webapp-dev.svc:8080/health
```

Пример предполагает существующий Service `webapp` и endpoint `/health`. `--fail` превращает HTTP-ошибку в неуспешное завершение команды. Job ограничен общим временем выполнения, успешный hook удаляется по `HookSucceeded`. Неуспех проверки делает операцию неуспешной.

Waves определяют очередность внутри фазы; hooks определяют назначение ресурса в жизненном цикле синхронизации. [Документация о фазах и волнах](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/).

## 12. AppProject: границы команды

Слайд 18.

**AppProject** ограничивает допустимые источники, назначения и типы ресурсов для группы приложений.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-web
  namespace: argocd
spec:
  sourceRepos:
    - https://git.example.org/team/config.git
  destinations:
    - server: https://kubernetes.default.svc
      namespace: webapp-dev
    - server: https://kubernetes.default.svc
      namespace: webapp-prod
  clusterResourceWhitelist: []
  namespaceResourceBlacklist:
    - group: rbac.authorization.k8s.io
      kind: Role
    - group: rbac.authorization.k8s.io
      kind: RoleBinding
```

Приложение выбирает этот проект через `spec.project: team-web`.

В примере разрешён один Git-репозиторий и два namespace назначения. Cluster-scoped-ресурсы не разрешены, а среди namespaced-ресурсов дополнительно запрещены Role и RoleBinding.

**Namespace является cluster-scoped-ресурсом.** Поэтому при таких ограничениях namespace готовит администратор; пример с wave для Namespace из предыдущего раздела потребует другого набора разрешений. `CreateNamespace=true` не обходит ограничения проекта.

AppProject задаёт правила Argo CD, но не заменяет Kubernetes RBAC и ресурсные ограничения из [лекции 3](03-kubernetes-resource-management.md).

## 13. Роли проекта и окна синхронизации

Слайд 19.

Роль отвечает на вопрос «кто и что может сделать», окно - «когда разрешена синхронизация».

Дополняющий фрагмент `AppProject.spec`:

```yaml
roles:
  - name: operator
    groups:
      - web-operators
    policies:
      - "p, proj:team-web:operator, applications, get, team-web/*, allow"
      - "p, proj:team-web:operator, applications, sync, team-web/*, allow"
syncWindows:
  - kind: allow
    schedule: "0 10 * * 1-5"
    duration: 8h
    timeZone: Europe/Moscow
    applications:
      - "*-prod"
    manualSync: false
```

Группа `web-operators` получает просмотр и синхронизацию приложений проекта. В приведённом окне приложения с именем `*-prod` можно синхронизировать по будням с 10:00 до 18:00 по московскому времени. `manualSync: false` не включает исключение для ручного запуска вне окна. [Документация об окнах синхронизации](https://argo-cd.readthedocs.io/en/stable/user-guide/sync_windows/).

Разрешение роли само по себе не отменяет расписание и остальные ограничения проекта.

## 14. ApplicationSet и App-of-Apps

Слайды 20-21.

**ApplicationSet** генерирует несколько Application из списка или другого источника параметров. Пример создаёт приложения для `dev` и `prod`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: webapp-environments
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - list:
        elements:
          - env: dev
          - env: prod
  template:
    metadata:
      name: "webapp-{{.env}}"
    spec:
      project: team-web
      source:
        repoURL: https://git.example.org/team/config.git
        targetRevision: main
        path: "apps/webapp/overlays/{{.env}}"
      destination:
        server: https://kubernetes.default.svc
        namespace: "webapp-{{.env}}"
```

Получаются `webapp-dev` и `webapp-prod`. Пути overlays должны существовать, namespaces должны быть подготовлены согласно правилам проекта. `missingkey=error` позволяет обнаруживать отсутствующие параметры шаблона.

ApplicationSet Controller создаёт и сопровождает описания Application. Доставку ресурсов выполняет Application Controller.

**App-of-Apps** - другой способ композиции: родительское Application указывает на каталог с уже описанными дочерними Application.

```text
Root Application
  -> applications/
       webapp-dev.yaml  -> Application -> ресурсы dev
       webapp-prod.yaml -> Application -> ресурсы prod
```

Родитель применяет дочерние Application в namespace Argo CD. Репозиторий bootstrap требует административного контроля: изменение дочерних приложений может менять источники, проекты и назначения доставки.

| Подход | Откуда берутся дочерние Application |
| --- | --- |
| ApplicationSet | Генерируются из параметров и шаблона |
| App-of-Apps | Уже описаны отдельными манифестами в каталоге |

## 15. Доступ к закрытому Git

Слайд 22.

Argo CD может использовать Secret с настройками репозитория:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: team-git-repository
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  type: git
  url: https://git.example.org/team/config.git
  username: git-reader
  password: "<READ_ONLY_TOKEN>"
```

Метка определяет назначение Secret, токен предоставляет чтение Git. Здесь указан только заполнитель: реальный токен в репозиторий не коммитят.

Доступ к Git, разрешение источника в AppProject и право изменять Kubernetes-ресурсы проверяются отдельно. Успешное чтение репозитория ещё не означает разрешённую доставку его содержимого.

## 16. Диагностика и возврат конфигурации

Слайд 23.

```bash
argocd app get webapp-dev
argocd app diff webapp-dev
argocd app sync webapp-dev
argocd app wait webapp-dev --sync --health
```

Порядок поиска причины:

1. **Источник:** доступен ли репозиторий, верны ли revision и path?
2. **Рендеринг:** собирается ли overlay или chart с выбранными values?
3. **Применение:** разрешает ли действие AppProject и Kubernetes API?
4. **Ресурсы:** что показывают Events, status, logs и health?
5. **Приложение:** восстановился ли сервис в пользовательском сценарии?

Возврат конфигурации фиксируют в Git: например, возвращают прежний tag образа или отключают ошибочный feature flag. После этого контроллер доставляет исправленное желаемое состояние.

Если исправить только кластер, а в Git оставить ошибочную конфигурацию, self-heal может восстановить именно ошибочный вариант. Откат конфигурации также не отменяет изменения прикладных данных, о чём шла речь в [лекции о Helm](04-application-configuration.md).

## 17. Почему после изменения ConfigMap может требоваться restart

Дополнение по [заметкам с занятия](06-gitops-in-class.md), связано со слайдами 3 и 23.

Успешный sync ConfigMap означает обновление API-объекта. Приложение должно ещё получить и использовать новые значения.

| Способ использования ConfigMap | Что происходит при изменении |
| --- | --- |
| Переменные окружения контейнера | Уже работающий контейнер не получает новые значения; нужно пересоздание Pod |
| Обычное подключение как volume | Файлы обновляются с задержкой; приложение должно уметь их перечитывать |
| Подключение через `subPath` | Автоматического обновления файлов нет |
| Генератор Kustomize с hash в имени | Изменение распознаваемой ссылки в шаблоне Deployment меняет шаблон Pod и запускает rollout |

Поэтому в примере с занятия после sync потребовался restart Deployment. Это зависит от способа чтения настроек, а не является обязательным шагом после любого изменения ConfigMap. [Документация об обновлении ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/#mounted-configmaps-are-updated-automatically).

Пример явного перезапуска, когда он нужен выбранному способу конфигурирования:

```bash
kubectl rollout restart deployment/webapp -n webapp-dev
kubectl rollout status deployment/webapp -n webapp-dev
```

В постоянном процессе доставки обновление Pod следует связывать с версией конфигурации. Для Kustomize такой механизм разобран в [разделе о генераторах](04-application-configuration.md#10-генераторы-configmap-и-secret).

## 18. Связь с предыдущими лекциями

Сводка по материалам лекции.

| Задача | Механизм |
| --- | --- |
| Сформировать YAML для окружения | Helm или Kustomize |
| Зафиксировать желаемую версию | Git |
| Получать и непрерывно согласовывать конфигурацию | GitOps-контроллер |
| Описать источник и назначение Argo CD | Application |
| Ограничить источники, назначения и действия команды | AppProject и RBAC |
| Создать несколько описаний приложений | ApplicationSet или App-of-Apps |
| Сохранить данные независимо от Pod | PVC, PV и система хранения |
| Убедиться в результате доставки | Sync Status, Health и проверка самого сервиса |
