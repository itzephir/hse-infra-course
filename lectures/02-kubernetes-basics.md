# Лекция 2. Основы Kubernetes

[К содержанию курса](../README.md) · [Предыдущая лекция](01-introduction.md)

Тема: архитектура и базовые объекты платформы. Дата на слайдах: 08.10.2026. Источник: `Л2.pdf`, 44 слайда; автор PDF — Максим Новосельцев.

Конспект следует презентации; определения и связи между компонентами изложены своими словами. YAML-примеры адаптированы из слайдов, номера слайдов указаны по разделам. Команды приведены как учебная шпаргалка и не выполнялись на реальном кластере.

## 1. Оркестрация и желаемое состояние

Слайды 1–4.

Контейнеру нужны узел для запуска, правила восстановления после сбоя, число копий, способ обновления и адреса других сервисов. Kubernetes управляет этими задачами через API-объекты и контроллеры.

- `spec` — желаемое состояние объекта.
- `status` — наблюдаемое состояние.
- **Reconciliation loop** — повторяющийся цикл сравнения этих состояний и устранения расхождений.

Пример: задано `replicas: 3`, работают два Pod. Контроллер создаёт недостающий Pod. Эта модель предполагает, что Pod управляются соответствующим контроллером; отдельно созданный Pod сам по себе не задаёт число реплик.

## 2. Control plane

Слайды 5–10.

**Control plane** хранит состояние и управляет кластером. **Worker nodes** выполняют приложения. Основное взаимодействие компонентов идёт через Kubernetes API.

| Компонент | Задача | Последствие недоступности компонента без работающей резервной копии |
| --- | --- | --- |
| `kube-apiserver` | Публикует HTTP API, проверяет запросы, выполняет authentication, authorization и admission; читает и пишет состояние через etcd | Нельзя нормально управлять кластером; уже запущенные контейнеры могут продолжить работу |
| `etcd` | Хранит состояние API-объектов, обеспечивает согласованность и наблюдение за изменениями | Потеря quorum блокирует запись нового состояния |
| `kube-scheduler` | Выбирает Node для Pod, которому ещё не назначен узел | Новые неназначенные Pod остаются в `Pending` |
| `kube-controller-manager` | Выполняет встроенные циклы согласования: Deployment, ReplicaSet, Node, Job, EndpointSlice и другие | Автоматическое устранение расхождений нарушается; работающие контейнеры могут сохраниться |

**Authentication** определяет, кто отправил запрос. **Authorization** проверяет разрешение на действие. **Admission** дополнительно проверяет или изменяет запрос перед сохранением объекта.

etcd хранит объекты Kubernetes, но не образы контейнеров, логи приложения и содержимое PersistentVolume. Поэтому резервирование etcd и резервирование прикладных данных — отдельные задачи.

Scheduler учитывает requests, taints, affinity, топологию и ограничения томов. Он назначает узел, а фактический запуск выполняют компоненты этого узла.

## 3. Компоненты узла

Слайды 11–14.

| Компонент | Роль |
| --- | --- |
| `kubelet` | Получает PodSpecs своего узла, управляет выполнением Pod, выполняет probes и публикует status |
| Container runtime | Загружает образы, создаёт Pod sandbox, запускает и останавливает контейнеры |
| `kube-proxy` | Наблюдает за Service и EndpointSlice, настраивает перенаправление трафика к backend endpoints |

kubelet обращается к runtime через **CRI** по gRPC. Примеры runtime из лекции — `containerd` и `CRI-O`, поддерживающие CRI v1.

При сбое kubelet управление локальными контейнерами и обновление состояния нарушаются. При сбое runtime новые контейнеры не запускаются. Уже работающие контейнеры не обязательно останавливаются одновременно со сбоем управляющего компонента.

В рассмотренной схеме kube-proxy реализует доступ через Service с помощью механизмов ОС: например, iptables или nftables. CoreDNS отвечает за разрешение имён сервисов; перенаправление трафика к их backend выполняет сетевой механизм Service.

## 4. Создание Pod и расширения Kubernetes

Слайды 15–16.

1. `kubectl` отправляет запрос в API Server.
2. API Server проверяет запрос и сохраняет объект через etcd.
3. Scheduler находит Pod без назначенного узла и записывает назначение через API.
4. kubelet выбранного узла получает описание Pod.
5. Runtime запускает контейнеры.
6. kubelet продолжает отправлять status через API Server.

Схема на слайде показывает логическую последовательность. Scheduler и kubelet взаимодействуют через API Server, а не подключаются напрямую к etcd.

| Интерфейс или компонент | Область ответственности |
| --- | --- |
| CNI | Сеть контейнеров |
| CRI | Взаимодействие kubelet с container runtime |
| CSI | Подключение хранилищ |
| CoreDNS | DNS-имена сервисов |

## 5. Манифесты, namespace и метки

Слайды 17–20.

Манифест — описание API-объекта в YAML. В примере Deployment:

| Поле | Смысл |
| --- | --- |
| `apiVersion` | Группа и версия API: например, `apps/v1` |
| `kind` | Тип объекта: например, `Deployment` |
| `metadata` | Имя, namespace, метки и другая информация об объекте |
| `spec` | Желаемое состояние |

У ConfigMap и Secret данные задаются в `data` или `stringData`, а не в `spec`: набор полей зависит от типа объекта.

**Namespace** задаёт область имён. **Labels** — метки вида `app: web`. **Selector** выбирает объекты по меткам; например, Service находит Pod с `app: web`.

Пример `namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: lecture-demo
  labels:
    course: infrastructure
```

```bash
kubectl apply -f namespace.yaml
kubectl get namespace lecture-demo
```

## 6. kubectl и kubeconfig

Слайды 21–26.

`kubectl` — клиент Kubernetes API. Чтобы выполнить команду, он выбирает конфигурацию подключения, обращается к API Server по HTTPS и получает объекты или сообщение об ошибке.

Порядок выбора kubeconfig:

1. `--kubeconfig ./config`: используется один явно указанный файл.
2. Переменная `KUBECONFIG`: используется список файлов с объединением конфигураций.
3. `$HOME/.kube/config`: путь по умолчанию, если первые два источника не заданы.

| Поле kubeconfig | Содержимое |
| --- | --- |
| `clusters` | Адрес API Server и параметры проверки его сертификата |
| `users` | Способ аутентификации: сертификат, токен или внешний механизм |
| `contexts` | Связка cluster, user и namespace по умолчанию |
| `current-context` | Активный context |

Шпаргалка работы с контекстом:

```bash
kubectl config get-contexts
kubectl config current-context
kubectl config use-context minikube
kubectl config set-context --current --namespace=lecture-demo
kubectl config view --minify
kubectl auth whoami
kubectl cluster-info
```

`kubectl config view --raw` может вывести чувствительные данные. Перед изменением объектов следует проверить выбранный context и namespace.

Основные команды:

| Команда | Назначение |
| --- | --- |
| `kubectl apply -f app.yaml` | Создать или обновить объекты из файла |
| `kubectl get pods -n lecture-demo` | Посмотреть Pod |
| `kubectl get all -n lecture-demo` | Посмотреть основные типы объектов; это не полный список всех ресурсов |
| `kubectl describe pod <name> -n lecture-demo` | Посмотреть состояние и события Pod |
| `kubectl logs <name> -n lecture-demo` | Прочитать логи контейнера |
| `kubectl exec -it <name> -n lecture-demo -- sh` | Запустить shell внутри контейнера, если он доступен в образе |
| `kubectl delete -f app.yaml` | Удалить объекты, перечисленные в файле |

Порядок диагностики: `get` → `describe` → `logs` → `exec`. Сначала выясняем, какой объект не готов, затем читаем его состояние и Events, после этого исследуем приложение.

## 7. Pod и его состояние

Слайды 27–29.

**Pod** — единица запуска, содержащая один или несколько связанных контейнеров. Они используют общий сетевой контекст: IP и пространство портов. Определённые для Pod volumes могут подключаться к его контейнерам.

Пример `pod.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: pod-demo
  namespace: lecture-demo
  labels:
    app: pod-demo
spec:
  containers:
    - name: nginx
      image: nginx:1.27-alpine
      ports:
        - containerPort: 80
```

Образ сохранён из учебного примера лекции; его версия не является рекомендацией для production.

Основные фазы на слайде: `Pending`, `Running`, `Succeeded`, `Failed`. Это упрощённая схема жизненного цикла; статус `Running` сам по себе не означает готовность принимать трафик.

| Проверка или настройка | Вопрос |
| --- | --- |
| Readiness probe | Готов ли контейнер обслуживать запросы? |
| Liveness probe | Требуется ли перезапуск контейнера? |
| Startup probe | Завершился ли запуск контейнера? |
| Requests / limits | Какие ресурсы запросить и как ограничить потребление? |

Прямое создание Pod удобно для изучения. Для приложения, которому нужны реплики и обновления, обычно используют Deployment.

## 8. ReplicaSet и Deployment

Слайды 30–34.

**ReplicaSet** поддерживает заданное число Pod, соответствующих selector. Если управляемый Pod удалён, контроллер создаёт замену.

Пример `replicaset.yaml`:

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: web-rs
  namespace: lecture-demo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rs-demo
  template:
    metadata:
      labels:
        app: rs-demo
    spec:
      containers:
        - name: nginx
          image: nginx:1.27-alpine
```

Selector должен совпадать с метками в шаблоне Pod. Метка самого ReplicaSet и метки создаваемых им Pod относятся к разным объектам.

**Deployment** управляет ReplicaSet и добавляет механизм обновлений и историю ревизий шаблона Pod.

```text
Deployment → ReplicaSet → Pods
```

Пример `deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: lecture-demo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: nginx
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
```

При **rolling update** Deployment постепенно увеличивает число Pod нового ReplicaSet и уменьшает число старых. Схема на слайде показывает постепенную замену `v1` на `v2`; конкретное количество одновременно работающих Pod зависит от настроек обновления.

**Rollback** возвращает предыдущую ревизию шаблона Pod. Он не откатывает автоматически данные базы или другие независимые объекты конфигурации.

## 9. Service и обнаружение сервисов

Слайды 35–38.

IP отдельных Pod могут меняться при пересоздании. **Service** предоставляет стабильную точку доступа к набору backend endpoints. В примере из лекции набор Pod определяется selector.

| Тип Service | Назначение |
| --- | --- |
| `ClusterIP` | Доступ через адрес внутри кластера; тип по умолчанию |
| `NodePort` | Доступ через выделенный порт на узлах |
| `LoadBalancer` | Интеграция с реализацией внешнего балансировщика |
| `ExternalName` | DNS-алиас на внешнее имя |

Пример `service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
  namespace: lecture-demo
spec:
  type: ClusterIP
  selector:
    app: web
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 80
```

- `port` — порт Service.
- `targetPort` — порт backend, на который перенаправляется трафик.
- `containerPort` в Pod описывает порт контейнера; он не создаёт Service и не публикует приложение наружу.

Для Service `backend` в namespace `default` на слайде указано имя `backend.default.svc.cluster.local`. Суффикс `cluster.local` — пример домена кластера, он может быть настроен иначе.

CoreDNS разрешает имя Service. EndpointSlices описывают endpoints и их состояние, а сетевой механизм Service направляет трафик к подходящим backend.

```bash
kubectl get svc,endpointslices -n lecture-demo
```

## 10. ConfigMap

Слайды 39–40.

**ConfigMap** хранит обычную конфигурацию отдельно от образа. Значения можно передать контейнеру через environment variables или файлы в volume.

Пример `configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config
  namespace: lecture-demo
data:
  LOG_LEVEL: "info"
  WELCOME_TEXT: "Hello"
```

Фрагмент контейнера в `spec.template.spec.containers` Deployment:

```yaml
- name: nginx
  image: nginx:1.27-alpine
  envFrom:
    - configMapRef:
        name: web-config
```

Так все ключи ConfigMap передаются как переменные окружения. Чтобы они влияли на поведение, приложение должно использовать эти переменные.

## 11. Secret

Слайды 41–42.

**Secret** предназначен для паролей, токенов и ключей. Base64 — кодировка; сама по себе она не обеспечивает секретность. Защита требует ограничений доступа, включая RBAC, и настройки шифрования данных в хранилище.

Пример `secret.yaml` с вымышленным значением из лекции:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: web-secret
  namespace: lecture-demo
type: Opaque
stringData:
  API_TOKEN: demo-token
```

`stringData` позволяет указать текстовое значение без ручного Base64-кодирования.

Фрагмент контейнера в Deployment:

```yaml
- name: nginx
  image: nginx:1.27-alpine
  env:
    - name: API_TOKEN
      valueFrom:
        secretKeyRef:
          name: web-secret
          key: API_TOKEN
```

`secretKeyRef` передаёт один выбранный ключ. ConfigMap и Secret в этих примерах находятся в том же namespace, что и Pod.

## 12. Способы запуска Kubernetes

Слайды 43–44.

| Подход | Примеры на слайде | Кто управляет платформой |
| --- | --- | --- |
| Managed Kubernetes | EKS, GKE, AKS | Часть инфраструктуры обслуживает провайдер |
| Self-managed | kubeadm, Kubespray | Кластер обслуживает собственная команда |
| Local | Minikube, kind, k3d | Локальный инструмент создаёт учебный или тестовый кластер |

Способы развёртывания различаются тем, как создаются control plane, etcd и worker nodes, какие компоненты устанавливаются на узлах и какие задачи эксплуатации остаются у команды.

Связи базовых объектов:

```text
Deployment → ReplicaSet → Pods ← Service выбирает по labels
                            ↑
                     ConfigMap и Secret
```

Deployment управляет жизненным циклом приложения, Service обеспечивает доступ, ConfigMap и Secret передают настройки.
