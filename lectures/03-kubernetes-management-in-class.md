Несколько команд используют один кластер

Необходима изоляция

первый вариант - развернуть еще один кластер
это рабочий подход, но возникают проблемы: как дать доступы для бд, как достучаться - в целом решить можно, например внешним апи - но может быть неудобно

namespace
логическая область внутри одного кластера
имена объектов уникальны внутри области
один объект принадлежит только одному namespace
namespaces не бывают вложенными

внутри namespace: Pod, Deployment, Service, ConfigMap, Secret, Role, ServiceAccount
на уровне кластера: Node, Namespace, PersistentVolume, StorageClass, ClusterRole, ClusterRoleBinding

модели:
- namespace на команду
- namespace на проект
- разделение development, testing, production
- отдельные области для системных компонентов

ограничения namespace:
- не блокирует сетевой трафик между Pod
- не ограничивает CPU и память
- не выдает и не запрещает доступ к API
- не создает отдельные worker nodes
- не является строгой границей безопасности

проблемы:
- несколько команд используют общие ноды
- один контейнер может занять свободные ресурсы - например одна тяжелая джоба бекенда сожрала ресурсы фронта
- scheduler планирует по requests - сейчас узнаем
- kubelet и runtime применяют limits

resource requests:
launching pod, request: 500m CPU, request: 512Mi => scheduler -> \[{node A, free 200m}, {node B, free 2000m}]

free cpu != used cpu
free cpu := reserved cpu

cpu:
- превышение limit
- контейнер получает меньше процессорного времени
- процесс обычно продолжает работать
- симптом: рост latency

LimitRange
лимит на resource request

Манифест Pod без resources -> API Server -> LimitRanger добавляет defaults -> проверка min и max

ResourceQuota
- суммарный бюджет namespace
- ограничивает requests и limits
- ограничивает количество API-объектов
- отклоняет при превышении hard

Что можно ограничивать квотой
requests.cpu
requests.memory
limits.cpu
limits.memory
requests.storage
pods
services
secrets
