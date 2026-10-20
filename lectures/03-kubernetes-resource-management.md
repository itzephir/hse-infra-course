# Лекция 3. Управление ресурсами и мультиарендность

[К содержанию курса](../README.md) · [Предыдущая лекция](02-kubernetes-basics.md)

Тема: Namespace, requests и limits, LimitRange, ResourceQuota, RBAC и ServiceAccount. Дата на слайдах: 13.10.2026. Источник: `Л3.pdf`, 44 слайда; автор PDF - Максим Новосельцев. Учтены [исходные заметки с занятия](03-kubernetes-management-in-class.md).

Определения и связи изложены своими словами, номера слайдов указаны по разделам. YAML-примеры адаптированы из презентации; дополнительные уточнения сопровождаются ссылками на документацию. Команды служат примерами и не выполнялись на кластере.

## 1. Один кластер для нескольких команд

Слайды 1-5.

**Мультиарендность (multi-tenancy)** - совместное использование кластера несколькими командами, проектами или окружениями. Например, в одном Kubernetes работают production команды A, testing команды B и системные компоненты платформы.

У них общие worker nodes и control plane. Поэтому нужно определить:

- где находятся объекты каждой команды;
- сколько CPU, памяти и API-объектов ей разрешено запрашивать;
- какие действия пользователи могут выполнять через API;
- от чьего имени приложения обращаются к API;
- как разделяются сетевой трафик и выполнение на узлах.

Из заметок с занятия: можно выделить каждой команде отдельный кластер. Это даёт отдельную инфраструктуру, но требует настроить взаимодействие между кластерами и доступ к общим сервисам, например базе данных. Namespace позволяет организовать логическое разделение внутри одного кластера.

| Механизм | За что отвечает |
| --- | --- |
| Namespace | Область имён и объектов |
| Requests / limits | Ресурсы контейнера при планировании и выполнении |
| LimitRange | Значения по умолчанию и ограничения для отдельного объекта |
| ResourceQuota | Суммарный бюджет namespace |
| RBAC | Разрешённые действия через Kubernetes API |
| ServiceAccount | Идентичность приложения |

Эти механизмы дополняют друг друга. Одного Namespace недостаточно для полной изоляции.

## 2. Namespace: область объектов

Слайды 6-10.

**Namespace** - логическая область внутри кластера. Имена объектов одного типа уникальны в пределах namespace: например, в `team-a` и `team-b` могут существовать разные Deployment с одинаковым именем `reports`.

Объект с областью namespace принадлежит ровно одному namespace. Namespaces не вкладываются друг в друга. Объекты уровня кластера к namespace не относятся.

| Внутри namespace (namespaced) | На уровне кластера (cluster-scoped) |
| --- | --- |
| Pod, Deployment, Service | Node, Namespace |
| ConfigMap, Secret | PersistentVolume, StorageClass |
| Role, RoleBinding, ServiceAccount | ClusterRole, ClusterRoleBinding |

Типичные варианты разделения: namespace на команду, на проект, на окружение (`development`, `testing`, `production`), отдельные namespaces для системных компонентов.

Namespace сам по себе:

- не блокирует сетевой трафик между Pod;
- не ограничивает CPU и память;
- не выдаёт и не запрещает доступ к API;
- не выделяет отдельные worker nodes;
- не создаёт строгую границу безопасности.

Пример `namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: team-a
  labels:
    owner: analytics
    environment: production
```

```bash
kubectl apply -f namespace.yaml
kubectl get namespaces
kubectl get pods -n team-a
```

После создания namespace к нему можно привязать квоты, ограничения ресурсов и правила доступа.

## 3. Noisy neighbor и resource requests

Слайды 11-12.

**Noisy neighbor («шумный сосед»)** - приложение, которое активно потребляет общие ресурсы и мешает остальным. Пример из заметок: тяжёлая задача backend заняла ресурсы узла, из-за чего frontend стал работать медленнее.

**Request** - заявленная потребность контейнера в ресурсе. Scheduler использует requests при выборе Node. Request не задаёт верхнюю границу потребления: при наличии ресурсов контейнер может использовать больше.

Для CPU `1000m = 1 CPU`, `500m = 0.5 CPU`, `100m = 0.1 CPU`. Для памяти `Mi` и `Gi` - двоичные единицы: `1 Gi = 1024 Mi`.

На слайде Pod запрашивает `500m` CPU и `512Mi` памяти:

| Узел | Остаток CPU для планирования | Решение по CPU |
| --- | --- | --- |
| Node A | `200m` | Недостаточно для request `500m` |
| Node B | `2 CPU` | Достаточно; нужно также проверить память и остальные условия |

Уточнение к заметкам: «свободный CPU» в этой схеме означает остаток после учёта requests уже назначенных Pod. Это не текущая незагруженная доля процессора.

```text
Остаток для планирования ≈ Node allocatable - уже учтённые requests
```

Например, на узле для Pod доступно `2 CPU`, из них `1800m` уже учтены в requests. Осталось `200m`, поэтому новый Pod с request `500m` не поместится, даже если существующие приложения сейчас почти не используют CPU. Scheduler также проверяет память и другие ограничения размещения. [Документация о планировании по requests](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#how-pods-with-resource-requests-are-scheduled).

## 4. Resource limits: CPU и память

Слайды 13-15.

**Limit** - верхняя граница потребления ресурса контейнером. kubelet передаёт настройки runtime; в Linux ограничения применяются механизмами ядра, в частности cgroups.

| Ресурс | Что происходит при достижении ограничения | Типичный симптом |
| --- | --- | --- |
| CPU | Throttling: контейнер получает меньше процессорного времени | Растёт время ответа, процесс обычно продолжает работать |
| Memory | При нехватке памяти в пределах лимита процесс может быть завершён OOM killer | `OOMKilled`, возможен перезапуск контейнера |

Перезапуск зависит от политики перезапуска и того, какой процесс был завершён. Limit не резервирует соответствующую мощность узла и не гарантирует производительность.

Фрагмент списка контейнеров в `spec.template.spec.containers` Deployment:

```yaml
- name: api
  image: example/reports:1.0
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 256Mi
```

Scheduler учитывает request `100m` CPU и `128Mi` памяти. При выполнении CPU ограничен `500m`, память - `256Mi`. Request каждого ресурса должен быть не больше соответствующего limit.

В лекции ресурсы задаются для каждого контейнера. `example/reports:1.0` - условный образ из презентации.

## 5. QoS-классы Pod

Слайд 16.

**QoS (Quality of Service)** - класс Pod, определяемый настройками CPU и памяти. Он влияет на поведение при дефиците ресурсов Node.

Для рассмотренной в лекции настройки ресурсов на уровне контейнеров:

| Класс | Условия |
| --- | --- |
| `BestEffort` | Ни у одного контейнера нет requests и limits для CPU и памяти |
| `Guaranteed` | У каждого контейнера заданы положительные request и limit для CPU и памяти; для каждого ресурса request равен limit |
| `Burstable` | Задан хотя бы один request или limit CPU/памяти, но условия `Guaranteed` не выполнены |

Пример из предыдущего раздела относится к `Burstable`: requests и limits различаются.

**Eviction** - удаление Pod с узла при нехватке ресурсов. `BestEffort` имеет меньшую защиту, `Guaranteed` - большую. При выборе кандидатов также учитываются приоритет Pod и потребление относительно requests; одного названия QoS недостаточно для предсказания результата.

`Guaranteed` не защищает контейнер от завершения при превышении собственного memory limit. Eviction Pod из-за состояния узла и OOM внутри контейнера - разные механизмы. [Документация о QoS](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/).

## 6. LimitRange: правила для отдельного объекта

Слайды 17-19.

**LimitRange** действует внутри одного namespace. Он задаёт значения по умолчанию и проверяет допустимые параметры ресурсов.

| Поле | Назначение |
| --- | --- |
| `defaultRequest` | Request по умолчанию |
| `default` | Limit по умолчанию |
| `min` / `max` | Минимальные / максимальные допустимые requests и limits |
| `maxLimitRequestRatio` | Максимальное отношение limit к request |

Пример `limitrange.yaml` со слайда:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: container-limits
  namespace: team-a
spec:
  limits:
    - type: Container
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      default:
        cpu: 500m
        memory: 256Mi
      max:
        cpu: "2"
        memory: 1Gi
```

Для контейнера без `resources` будут добавлены requests `100m` / `128Mi` и limits `500m` / `256Mi`. Явно заданные значения также должны проходить ограничения; например, limit памяти `2Gi` превысит `max: 1Gi`.

```text
Запрос на создание Pod
  -> API Server
  -> LimitRanger добавляет недостающие defaults
  -> проверяются ограничения
  -> допустимый объект сохраняется, нарушение отклоняется
```

Нарушение ограничений LimitRange приводит к `403 Forbidden`. Изменение LimitRange не переписывает ресурсы уже работающих Pod. [Документация о LimitRange](https://kubernetes.io/docs/concepts/policy/limit-range/).

## 7. ResourceQuota: бюджет namespace

Слайды 20-25.

**ResourceQuota** ограничивает сумму заявленных ресурсов и количество объектов в одном namespace. LimitRange проверяет отдельный объект, ResourceQuota - общий бюджет.

| Что ограничивается | Ключи квоты |
| --- | --- |
| Суммарные requests CPU и памяти | `requests.cpu`, `requests.memory` |
| Суммарные limits CPU и памяти | `limits.cpu`, `limits.memory` |
| Запрошенное хранилище через PVC | `requests.storage` |
| Количество объектов | `pods`, `services`, `secrets`, `configmaps`, `persistentvolumeclaims` |

Ограничение количества объектов защищает также API и хранилище состояния от чрезмерного числа объектов.

Пример `quota.yaml`:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a-quota
  namespace: team-a
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 4Gi
    limits.cpu: "4"
    limits.memory: 8Gi
    pods: "10"
    services: "5"
    secrets: "20"
```

Просмотр квоты:

```bash
kubectl describe resourcequota team-a-quota -n team-a
```

Пример состояния со слайда:

| Ресурс | Used | Hard |
| --- | --- | --- |
| `requests.cpu` | `1200m` | `2` |
| `requests.memory` | `2Gi` | `4Gi` |
| `limits.cpu` | `2500m` | `4` |
| `limits.memory` | `5Gi` | `8Gi` |
| `pods` | `6` | `10` |
| `services` | `3` | `5` |

**Hard** - установленный максимум. **Used** - уже учтённая часть квоты. Для CPU и памяти здесь учитываются заявленные requests или limits, а не текущая загрузка по метрикам.

В примере осталось `800m` квоты `requests.cpu`. Новый Pod с request `900m` превысит бюджет, даже если CPU узлов простаивают. Чтобы объект был принят, он должен пройти все применимые ограничения одновременно.

Квота проверяется при создании и обновлении объектов. Превышение приводит к `403 Forbidden`. При этом Deployment может успешно создаться, а создание его Pod будет отклонено квотой; причину нужно искать в состоянии и событиях контроллеров. [Документация о ResourceQuota](https://kubernetes.io/docs/concepts/policy/resource-quotas/).

Совместная работа механизмов:

```text
LimitRange -> requests и limits контейнера -> ResourceQuota
defaults     параметры отдельного объекта    сумма и число объектов
```

Defaults полезны, когда квота требует указать requests и limits, а автор Pod их пропустил.

ResourceQuota не резервирует физические ресурсы Node, не гарантирует производительность, не ограничивает сетевой трафик и не перераспределяет бюджет между namespaces. Изменение квоты не переписывает существующие объекты и не удаляет автоматически Pod, если новый бюджет оказался меньше уже учтённого.

## 8. Authentication и authorization

Слайды 26-27.

| Этап | Вопрос | Примеры механизмов |
| --- | --- | --- |
| Authentication, аутентификация | Кто отправил запрос? | Сертификат, токен, OIDC |
| Authorization, авторизация | Разрешено ли ему действие? | RBAC и другие authorizers |

Успешная аутентификация не даёт автоматически права создавать или читать объекты.

**RBAC (Role-Based Access Control)** описывает разрешения через роли и их привязки к субъектам. При проверке учитываются субъект, действие, ресурс и область действия.

Пример: может ли пользователь `alice` выполнить `create` для ресурса `deployments` в namespace `team-a`?

## 9. Role, ClusterRole и привязки

Слайды 28-33.

Роль описывает набор разрешений. Binding связывает роль с пользователем, группой или ServiceAccount.

| Объект | Область и назначение |
| --- | --- |
| `Role` | Права на namespaced-ресурсы в одном namespace |
| `ClusterRole` | Набор прав уровня кластера или переиспользуемые права на namespaced-ресурсы |
| `RoleBinding` | Выдаёт права в своём namespace; ссылается на Role того же namespace или ClusterRole |
| `ClusterRoleBinding` | Выдаёт права из ClusterRole на уровне всего кластера |

**ClusterRole не обязательно означает доступ ко всему кластеру.** Например, ClusterRole `view`, назначенная через RoleBinding в `team-a`, даёт соответствующие права только в `team-a`. Если ту же роль назначить через ClusterRoleBinding, её права на namespaced-ресурсы будут действовать во всех namespaces.

RoleBinding не выдаёт доступ к cluster-scoped-ресурсам, например Node. Для такого доступа нужна соответствующая ClusterRoleBinding.

Правило роли состоит из:

- `apiGroups` - групп Kubernetes API, например `apps`; пустая строка `""` обозначает основную группу, где находятся Pod, Service, ConfigMap и Secret;
- `resources` - типов ресурсов в API, например `deployments`;
- `verbs` - разрешённых операций: `get`, `list`, `watch`, `create`, `update`, `patch`, `delete`.

Пример `role.yaml`:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: deployment-editor
  namespace: team-a
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
```

Роль позволяет читать, создавать и изменять Deployment в `team-a`. Она не выдаёт разрешение `delete` и прямые разрешения на Pod, Service или Secret.

Пример `rolebinding.yaml`, выдающий эту роль группе:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: developers
  namespace: team-a
subjects:
  - kind: Group
    name: analytics-developers
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: deployment-editor
  apiGroup: rbac.authorization.k8s.io
```

`subjects` отвечает на вопрос «кому», `roleRef` - «какая роль», namespace привязки - «где действуют права». Сама привязка не создаёт пользователей или группы во внешней системе аутентификации.

Разрешения RBAC складываются: отсутствие `delete` в этой роли не запрещает удаление, если оно разрешено другой привязкой. Отдельных правил `deny` в RBAC нет. [Документация о ролях и привязках RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/).

## 10. Проверка прав

Слайд 34.

`kubectl auth can-i` проверяет авторизацию без выполнения самой операции:

```bash
kubectl auth can-i create deployments.apps -n team-a
kubectl auth can-i delete secrets -n team-a
kubectl auth can-i --list -n team-a
```

Если единственная применимая роль - `deployment-editor` из примера, создание Deployment разрешено, удаление Secret - нет. Результат зависит от всех действующих привязок текущего пользователя.

Проверка от имени другого пользователя:

```bash
kubectl auth can-i create pods --as=alice -n team-a
```

`--as` использует impersonation и требует соответствующих прав. При проверке доступа через группу нужно также учитывать группы субъекта.

Успешная проверка авторизации не гарантирует создание объекта: затем запрос может быть отклонён, например, LimitRange или ResourceQuota.

## 11. Минимальные привилегии

Слайды 35-36.

Принцип минимальных привилегий: субъект получает только те действия и области доступа, которые нужны для его работы.

- Выдавать конкретные `verbs` и `resources`, избегать `*`.
- Ограничивать права нужным namespace.
- Разделять роли людей и приложений.
- Регулярно проверять RoleBinding и ClusterRoleBinding.

Почему некоторые разрешения требуют особого внимания:

| Разрешение | Возможность |
| --- | --- |
| Чтение Secret | Получение паролей, токенов и ключей |
| Создание Pod или изменение шаблона workload | Запуск кода, потенциальный доступ к данным и учётным записям, доступным этому workload |
| Управление привязками ролей | Передача прав другим субъектам в пределах разрешённых назначений |
| Доступ к Nodes и privileged workloads | Влияние на узлы и другие приложения |
| `cluster-admin` | Полный административный доступ |

В Kubernetes есть проверки против повышения привилегий: для назначения роли через binding нужно уже иметь её права в соответствующей области либо специальное право `bind`. Поэтому право изменять RoleBinding само по себе не означает возможность назначить любую роль. [Ограничения на создание и изменение привязок](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#restrictions-on-role-binding-creation-or-update).

## 12. ServiceAccount: идентичность приложения

Слайды 37-40.

| User / Group | ServiceAccount |
| --- | --- |
| Пользователь или группа из внешней системы аутентификации | Учётная запись для приложения |
| Обычные пользователи и группы не создаются как API-объекты Kubernetes | Создаётся как объект Kubernetes |
| Идентичность приходит, например, из сертификата или OIDC | Принадлежит конкретному namespace |

В каждом namespace автоматически создаётся ServiceAccount `default`. Если Pod не указывает `serviceAccountName`, используется эта учётная запись. Ей не следует выдавать широкие права для всех приложений namespace.

Для отдельного приложения создаётся собственная ServiceAccount, например `serviceaccount.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: report-generator
  namespace: team-a
automountServiceAccountToken: false
```

Полное имя субъекта:

```text
system:serviceaccount:team-a:report-generator
```

`automountServiceAccountToken: false` отключает автоматическое монтирование API-токена. Это подходит приложению, которому не нужно обращаться к Kubernetes API.

Deployment выбирает ServiceAccount в шаблоне Pod. Пример со слайдов дополнен обязательным selector и ресурсами из предыдущих разделов:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reports
  namespace: team-a
spec:
  replicas: 2
  selector:
    matchLabels:
      app: reports
  template:
    metadata:
      labels:
        app: reports
    spec:
      serviceAccountName: report-generator
      containers:
        - name: api
          image: example/reports:1.0
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
```

Все Pod, создаваемые из этого шаблона, используют `report-generator`. Назначение ServiceAccount определяет идентичность; права на API выдаются отдельно через RBAC.

## 13. Токены и RBAC для ServiceAccount

Слайды 41-42.

При автоматическом предоставлении Pod доступа к API используется короткоживущий токен:

```text
kubelet -> TokenRequest API -> токен ServiceAccount
                              -> projected volume в Pod
```

kubelet получает и обновляет токен. Долгоживущие токены, хранящиеся в Secret, не являются стандартным способом автоматической выдачи токенов Pod. [Документация о токенах ServiceAccount](https://kubernetes.io/docs/concepts/security/service-accounts/#assign-a-serviceaccount-to-a-pod).

Для приложения, которому нужно читать ConfigMap через API, схема прав выглядит так:

```text
Pod reports
  -> ServiceAccount report-generator
  -> RoleBinding
  -> Role с разрешением get configmaps
```

Пример привязки для ServiceAccount, дополняющий схему со слайда:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: config-reader
  namespace: team-a
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: report-config-reader
  namespace: team-a
subjects:
  - kind: ServiceAccount
    name: report-generator
    namespace: team-a
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: config-reader
```

Для использования API-токена приложением из предыдущего раздела нужно также включить его автоматическое монтирование, например задать `automountServiceAccountToken: true` в `spec.template.spec` Deployment. Binding выдаёт разрешение, но сам по себе не добавляет токен в контейнер.

## 14. Как механизмы работают вместе

Слайды 43-44.

Базовая модель для команды:

| Вопрос | Механизм |
| --- | --- |
| Где находятся объекты команды? | Namespace `team-a` |
| Какие ресурсы получит контейнер, если автор их не указал? | Defaults в LimitRange |
| Какие requests и limits допустимы для отдельного контейнера? | Ограничения в LimitRange |
| Каков общий бюджет команды? | ResourceQuota |
| Что разрешено участникам команды? | Роли и RoleBinding |
| От чьего имени работает приложение? | Отдельная ServiceAccount |
| Что приложение может делать через API? | RBAC для этой ServiceAccount |

Например, в namespace `team-a` запускаются два Pod `reports`. Каждый запрашивает `100m` CPU и `128Mi` памяти: вместе они учитывают `200m` и `256Mi` в квоте requests. Их суммарные limits - `1 CPU` и `512Mi`. Scheduler проверяет размещение по requests, ограничения выполнения применяются по limits, а доступ приложения к API определяется его ServiceAccount и привязками RBAC.

Этот набор задаёт области объектов, ресурсные бюджеты и права. Сетевая изоляция и выделение узлов остаются отдельными задачами: сам namespace, квота или роль их не обеспечивают.
