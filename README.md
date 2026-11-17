# Управление инфраструктурой данных

Конспекты лекций и домашние задания курса НИУ ВШЭ. Преподаватель: Максим Новосельцев.

Репозиторий: [itzephir/hse-infra-course](https://github.com/itzephir/hse-infra-course).

## Лекции

| № | Дата на слайдах | Тема | Конспект |
| --- | --- | --- | --- |
| 1 | 29.09.2026 | Введение в инфраструктуру | [Лекция 1](lectures/01-introduction.md) |
| 2 | 08.10.2026 | Основы Kubernetes: архитектура и базовые объекты | [Лекция 2](lectures/02-kubernetes-basics.md) |
| 3 | 13.10.2026 | Управление ресурсами и мультиарендность | [Лекция 3](lectures/03-kubernetes-resource-management.md) |
| 4 | 20.10.2026 | Управление конфигурацией: Helm и Kustomize | [Лекция 4](lectures/04-application-configuration.md) |
| 5 | 03.11.2026 | Хранение данных в Kubernetes: Volume, PV, PVC, CSI | [Лекция 5](lectures/05-kubernetes-storage.md) |
| 6 | 10.11.2026 | GitOps и Argo CD | [Лекция 6](lectures/06-gitops.md) |

## Домашние задания

| № | Тема | Материалы |
| --- | --- | --- |
| 2 | Развёртывание Kubernetes на bare metal | [Условие](hw/02/README.md) · [Решение](hw/02/solution.md) |
| 3 | Изоляция команд в Kubernetes | [Условие](hw/03/README.md) · [Решение](hw/03/solution.md) |
| 6 | Push- и pull-модели CD: лендинг, GHCR и Argo CD | [Условие](hw/06/README.md) · [Решение](hw/06/solution.md) |

## Структура

```text
lectures/                 Конспекты лекций
  01-introduction.md
  02-kubernetes-basics.md
  03-kubernetes-resource-management.md
  03-kubernetes-management-in-class.md  Исходные заметки с занятия
  04-application-configuration.md
  05-kubernetes-storage.md
  06-gitops.md
  06-gitops-in-class.md      Исходные заметки с занятия
hw/                       Домашние задания
  02/
    README.md             Условие задания
    solution.md           Сравнение способов развёртывания
  03/
    README.md             Условие задания
    solution.md           Облако для друзей: ресурсы, доступ и границы изоляции
    manifests/            Примеры конфигурации Kubernetes
  06/
    README.md             Условие задания
    solution.md           GitHub Actions, GHCR и Argo CD для лендинга Relay
    app/                  Самостоятельное приложение и Dockerfile
    manifests/            Общие ресурсы и overlays dev/prod
    argocd/               AppProject и Application для dev/prod
    workflows/            Примеры push-доставки GitHub Actions
    scripts/              Проверки контейнера, minikube, фиксация образа и push CD
    bootstrap/            Namespaces учебного стенда
```

Для каждого следующего задания создаётся каталог `hw/NN/`: условие хранится в `README.md`, готовое решение — в `solution.md`. Дополнительные файлы размещаются рядом с решением по мере необходимости.

## Формат материалов

Все текстовые материалы оформляются в Markdown и читаются в GitHub, стандартном превью VS Code и Obsidian. Используются обычные заголовки, списки, таблицы, блоки кода и относительные ссылки между файлами.

В VS Code достаточно открыть этот каталог и вызвать Markdown Preview. В Obsidian каталог можно открыть как хранилище. Специальные плагины для чтения конспектов не требуются.

В конспектах указаны исходные PDF и номера слайдов. Учебные команды и манифесты в блоках кода служат примерами; их наличие в конспекте не означает, что кластер был развёрнут или пример проверен запуском.

## Работа с репозиторием

После редактирования материалов:

```bash
git status
git add README.md lectures/ hw/
git commit -m "docs: update course materials"
git push
```

Локальные настройки редакторов, временные файлы и файлы доступа к инфраструктуре исключены через `.gitignore`. Настоящие токены, пароли и содержимое Secret не добавляются в репозиторий; в учебных примерах используются только вымышленные значения.
