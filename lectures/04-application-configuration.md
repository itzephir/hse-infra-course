# Лекция 4. Управление конфигурацией приложений

[К содержанию курса](../README.md) · [Предыдущая лекция](03-kubernetes-resource-management.md) · [Следующая лекция](05-kubernetes-storage.md)

Тема: Helm, Kustomize, шаблонизация и overlays. Дата на слайдах: 20.10.2026. Источник: `Л4.pdf`, 42 страницы; автор PDF - Максим Новосельцев.

Конспект следует презентации; определения и примеры изложены своими словами. Ссылки на страницы относятся к порядку страниц PDF: номера в колонтитулах местами пропущены и доходят до 44. Примеры адаптированы для объяснения отдельных механизмов; команды не выполнялись на кластере.

## 1. Зачем управлять конфигурацией

Страницы PDF 1-6.

Одно приложение разворачивается в нескольких окружениях. В `dev` достаточно одной реплики и небольших requests, в `prod` нужны несколько реплик, другой hostname, TLS и более строгие политики.

Если хранить независимые копии `deployment-dev.yaml`, `deployment-stage.yaml` и `deployment-prod.yaml`, общие исправления приходится переносить вручную. Со временем копии расходятся: например, новый probe добавили только в одно окружение.

Решение - общая основа и явно описанные различия:

```text
Общая конфигурация + параметры окружения
  -> сборка итоговых манифестов
  -> проверка
  -> Kubernetes API
```

**Helm** строит манифесты из шаблонов и значений. **Kustomize** преобразует обычные Kubernetes YAML с помощью overlays и patches. В обоих случаях кластер получает обычные API-объекты Kubernetes.

## 2. Helm: chart, release и repository

Страницы PDF 7-10.

**Helm** - пакетный менеджер для Kubernetes.

| Понятие | Значение |
| --- | --- |
| Chart | Пакет с метаданными, шаблонами и значениями по умолчанию |
| Values | Параметры, по которым шаблоны формируют манифесты |
| Release | Конкретная установка chart с именем, параметрами и историей ревизий |
| Repository | Источник, из которого получают charts |

Один chart можно установить несколько раз как независимые releases: например, `reports-dev` и `reports-prod`.

Типичная структура chart:

```text
myapp/
  Chart.yaml
  values.yaml
  values.schema.json
  templates/
    deployment.yaml
    service.yaml
    _helpers.tpl
    NOTES.txt
  charts/
  crds/
```

| Файл или каталог | Назначение |
| --- | --- |
| `Chart.yaml` | Имя, версия, описание и зависимости пакета |
| `values.yaml` | Значения параметров по умолчанию |
| `values.schema.json` | Необязательная схема проверки values |
| `templates/` | Шаблоны Kubernetes-ресурсов |
| `_helpers.tpl` | Именованные вспомогательные шаблоны |
| `NOTES.txt` | Сообщение пользователю после установки |
| `charts/` | Зависимые charts |
| `crds/` | Определения пользовательских типов ресурсов |

Схема, зависимости и вспомогательные файлы добавляются по необходимости. Пример `Chart.yaml`:

```yaml
apiVersion: v2
name: myapp
description: Web application
type: application
version: 0.3.0
appVersion: "1.8.2"
```

`version` - версия самого chart. `appVersion` - версия приложения, которую chart описывает. Изменение шаблонов может потребовать новой версии chart без изменения версии приложения.

## 3. Values и приоритет параметров

Страницы PDF 11-13.

Пример `values.yaml`:

```yaml
replicaCount: 2
image:
  repository: registry.example.com/myapp
  tag: "1.8.2"
  pullPolicy: IfNotPresent
service:
  port: 8080
resources:
  requests:
    cpu: 100m
    memory: 128Mi
```

Values образуют **интерфейс chart**: пользователь меняет поддерживаемые параметры, не редактируя шаблоны. Например, `replicaCount` управляет числом реплик, `image.tag` - версией образа.

Приоритет от меньшего к большему:

```text
values.yaml самого chart
  -> переопределения из parent chart для зависимости
  -> пользовательские файлы -f
  -> параметры --set / --set-string
```

Если передано несколько файлов `-f`, более поздний переопределяет совпадающие значения из предыдущих. `--set-string` позволяет явно сохранить строковый тип значения.

Например:

```bash
helm template demo ./myapp \
  -f values-dev.yaml \
  --set replicaCount=3 \
  --set-string image.tag=1.8.3
```

Даже если в `values-dev.yaml` указана одна реплика, итоговое значение будет `3`.

## 4. Как работают Helm templates

Страницы PDF 12, 14-16.

Helm вычисляет выражения Go templates в `{{ ... }}` до отправки манифестов в Kubernetes.

| Выражение | Откуда берётся значение |
| --- | --- |
| `.Values.replicaCount` | Из итогового набора values |
| `.Chart.Name`, `.Chart.Version` | Из метаданных chart |
| `.Release.Name` | Из имени конкретной установки |
| `.` | Текущий контекст шаблона |

Пример helper в `templates/_helpers.tpl`:

```gotmpl
{{- define "myapp.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name -}}
{{- end -}}
```

Имя `myapp.fullname` включает имя chart, чтобы уменьшить риск конфликта с helpers зависимостей. Сам helper не создаёт отдельный API-объект.

Шаблон `templates/deployment.yaml`, дополненный обязательными selector и labels:

```gotmpl
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "myapp.fullname" . }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/instance: {{ .Release.Name | quote }}
  template:
    metadata:
      labels:
        app.kubernetes.io/instance: {{ .Release.Name | quote }}
    spec:
      containers:
        - name: myapp
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - containerPort: {{ .Values.service.port }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

Для release `demo` и chart `myapp` имя Deployment получится `demo-myapp`. Kubernetes не видит `.Values` или `include`: после рендеринга это обычные поля YAML.

Основные средства шаблонизации:

| Средство | Назначение |
| --- | --- |
| `quote` | Оформить значение как строку в кавычках |
| `default` | Подставить запасное значение, если вход считается пустым |
| `required` | Остановить рендеринг, если обязательное значение отсутствует или пусто |
| `upper` | Преобразовать строку в верхний регистр |
| `if` | Условно включить ресурс или фрагмент |
| `range` | Повторить фрагмент для элементов коллекции |
| `define` / `include` | Объявить и вызвать именованный шаблон |
| `toYaml` / `nindent` | Преобразовать структуру в YAML и добавить перевод строки с отступом |

Pipeline передаёт результат следующей функции:

```gotmpl
{{ .Values.mode | default "safe" | quote }}
{{ required "image.tag is required" .Values.image.tag | quote }}
```

Внутри `range` текущий контекст меняется на элемент коллекции. Это нужно учитывать при обращении к полям chart и release. Ошибки шаблонов и отступов проверяют по **отрендеренному YAML**.

## 5. Рендеринг, проверка и основные команды Helm

Страницы PDF 17-18, 22-24.

`helm template` показывает результат без установки release:

```bash
helm lint ./myapp
helm template demo ./myapp -f values-dev.yaml
helm template demo ./myapp -f values-prod.yaml --debug
```

Эти проверки решают разные задачи: lint находит проблемы chart, схема values проверяет параметры, рендеринг показывает конечные ресурсы. Успешный рендеринг ещё не доказывает, что Kubernetes примет объекты или приложение запустится.

Жизненный цикл установки:

```bash
helm install demo ./myapp -f values-dev.yaml -n team-a --create-namespace
helm list -n team-a
helm status demo -n team-a
helm upgrade demo ./myapp -f values-prod.yaml -n team-a
helm history demo -n team-a
helm rollback demo 2 -n team-a
helm uninstall demo -n team-a
```

Здесь `demo` - имя release, `./myapp` - путь к chart, `team-a` - namespace установки.

При проектировании chart полезно держать отдельный ресурс в отдельном template, давать helpers имена с префиксом chart, проверять обязательные values и документировать установку и обновление. Слишком много условий превращают chart в сложную программу и затрудняют review.

## 6. Ревизии release и границы rollback

Страницы PDF 19-20.

```text
install -> revision 1
upgrade -> revision 2
upgrade -> revision 3
rollback к revision 2 -> новая revision 4
```

Rollback создаёт новую ревизию на основе выбранного прежнего состояния. История продолжает расти.

**Откат манифестов и откат данных - разные операции.** Если новая версия приложения изменила схему базы данных, возврат старого Deployment не отменяет миграцию. Нужны совместимые миграции, отдельный сценарий восстановления и, при необходимости, резервная копия.

Helm управляет состоянием release. Он не обеспечивает автоматический возврат всех данных приложения к моменту предыдущей установки.

## 7. Зависимости chart

Страница PDF 21.

В `Chart.yaml` можно описать зависимый chart, например PostgreSQL. Учебный фрагмент:

```yaml
dependencies:
  - name: postgresql
    version: "15.x.x"
    repository: https://charts.example.com
    condition: postgresql.enabled
```

```bash
helm dependency update ./myapp
```

`Chart.lock` фиксирует выбранные версии зависимостей. Subchart получает свой набор values; `condition` позволяет включать зависимость через параметр. Адрес и версия выше сохранены как условный пример презентации.

## 8. Kustomize: base и overlays

Страницы PDF 25-29, 33-34.

**Kustomize** собирает конфигурацию из обычных Kubernetes-манифестов. Вместо подстановок `{{ ... }}` используются декларативные преобразования и patches.

- **Base** - общая основа с ресурсами приложения. Она не ссылается на окружения и может собираться отдельно.
- **Overlay** - конфигурация окружения, которая подключает base и описывает отличия.
- **Patch** - изменение выбранных полей конкретного ресурса.

Типичная структура:

```text
app/
  base/
    deployment.yaml
    service.yaml
    kustomization.yaml
  overlays/
    dev/
      kustomization.yaml
    prod/
      kustomization.yaml
      patch-resources.yaml
```

`base/kustomization.yaml` перечисляет обычные Deployment и Service:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
```

`overlays/prod/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namespace: myapp-prod
patches:
  - path: patch-resources.yaml
```

`overlays/prod/patch-resources.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 4
  template:
    spec:
      containers:
        - name: myapp
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
```

Patch предполагает, что в base есть Deployment `myapp` с контейнером `myapp`. Он изменяет число реплик и requests, сохраняя остальные поля. Выбор объекта может уточняться через `target` в записи `patches`.

В `dev` можно задать одну реплику, тестовый hostname и подробное логирование; в `prod` - несколько реплик, другие requests, TLS и политики. Общие исправления остаются в base.

## 9. Встроенные transformations

Страницы PDF 26, 30.

| Поле Kustomization | Что меняет |
| --- | --- |
| `namePrefix`, `nameSuffix` | Имена ресурсов |
| `namespace` | Namespace собираемых namespaced-ресурсов |
| `images` | Имя образа или его tag |
| `labels`, `annotations` | Общие метаданные |
| `replicas` | Число реплик выбранного workload |

Пример отдельных настроек overlay:

```yaml
namePrefix: dev-
labels:
  - pairs:
      environment: dev
    includeSelectors: true
replicas:
  - name: myapp
    count: 1
images:
  - name: registry.example.com/myapp
    newTag: "1.8.3"
```

`includeSelectors: true` добавляет метки также в selectors. Это влияет на выбор Pod, поэтому метки нужно согласовывать между связанными ресурсами.

## 10. Генераторы ConfigMap и Secret

Страница PDF 31.

Генераторы создают объекты из файлов или переменных. Фрагмент `kustomization.yaml`:

```yaml
configMapGenerator:
  - name: app-config
    files:
      - application.properties
secretGenerator:
  - name: app-secret
    envs:
      - secret.env
generatorOptions:
  disableNameSuffixHash: false
```

По умолчанию имя получает суффикс, зависящий от содержимого, например `app-config-<hash>`. При изменении файла меняется имя объекта. Kustomize обновляет распознаваемые ссылки на него в собираемых ресурсах.

Если такая ссылка находится в шаблоне Pod Deployment, меняется шаблон и возникает основание для rollout. Обновление ConfigMap с постоянным именем само по себе не означает перезапуск Pod.

`secretGenerator` не делает исходный `secret.env` безопасным для публикации. Реальные пароли и ключи не хранят в открытом Git.

## 11. Сборка и применение Kustomize

Страницы PDF 32-33.

```bash
kubectl kustomize app/overlays/dev
kubectl diff -k app/overlays/prod
kubectl apply -k app/overlays/dev
kubectl get -k app/overlays/dev
kubectl delete -k app/overlays/dev
```

`-k` принимает каталог с `kustomization.yaml`. `kubectl kustomize` выводит собранный YAML; `apply -k` применяет результат к кластеру. Проверка результата и diff помогают увидеть изменения до применения.

Каждый overlay собирают отдельно: корректность `dev` не гарантирует корректность `prod`.

## 12. Как выбрать инструмент

Страницы PDF 35-40.

| Критерий | Helm | Kustomize |
| --- | --- | --- |
| Основная модель | Версионируемый пакет приложения | Общая основа и различия окружений |
| Входные данные | Templates и values | Обычные YAML, overlays и patches |
| История установки | Helm release и его ревизии | Собственного release нет |
| Распространение | Charts, repositories, зависимости | Структура репозитория с манифестами |
| Сильная сторона | Много вариантов установки для разных пользователей | Явные изменения контролируемых командой YAML |
| Сложность | Условия, контексты шаблонов, интерфейс values | Зависимость patches от base, глубокие цепочки overlays |

Helm подходит, когда приложение распространяют как пакет, нужны зависимости и отдельный жизненный цикл установки. Kustomize удобен, когда команда владеет исходными манифестами и хочет явно видеть небольшие различия окружений.

Инструменты можно сочетать: например, получить chart поставщика, зафиксировать values и передать результат рендеринга системе доставки. При сочетании нужно определить, кто формирует YAML, кто его применяет и кто ведёт историю изменений.

## 13. Проверка конфигурации в CI

Страницы PDF 41-42.

```text
Lint и схема values
  -> рендеринг всех поддерживаемых конфигураций
  -> проверка Kubernetes-объектов
  -> проверка политик и безопасности
  -> diff перед применением
```

Проверять нужно каждый поддерживаемый набор values и каждый overlay. Ошибка может проявляться только в `prod`, если конкретный ресурс создаётся условно или patch затрагивает отсутствующее поле.

Итоговая связь понятий: **Helm упаковывает приложение, values задают параметры, Kustomize собирает основу с изменениями, а итоговые манифесты описывают обычные объекты Kubernetes.**
