# Проверка работающего стенда hw6

Ниже зафиксирована первоначальная ручная доставка. Текущая политика автоматической доставки: любой push обновляет dev, main также обновляет prod; источником родительского Argo CD служит `gitops/hw6`.

[Решение](solution.md) · [Условие](README.md)

## Автоматическая доставка по веткам

- [Push в рабочую ветку](https://github.com/itzephir/hse-infra-course/actions/runs/44066685357) успешно выполнил build и `record-dev`; `record-prod` пропущен.
- Dev автоматически перешёл на source SHA `3e493ec7d33d1939f5dcb152c7e8b397a8d4864c` и digest `sha256:3048a0f1b155aa467206c6f1748efe545e76f2f6bb8dc4033a463d78743b33f7`.
- Prod при этом сохранил первоначальный source SHA и digest: рабочая ветка его не обновила.
- Действующие условия workflow: push без фильтра путей, любая исходная ветка → dev; `refs/heads/main` → также prod. Ветка `gitops/hw6` исключена как служебная.
- Родительский Application `relay-hw6-delivery` читает `applications/` служебной ветки. Dev имеет волну 0, prod — 1; оценка здоровья проверяет выбранные source SHA и image override.
- В CI нет self-hosted runner, kubeconfig или доступа к Kubernetes API: доставка выполняется только контроллерами Argo CD.

## Первоначальная сборка и опубликованный образ

- [Успешный запуск GitHub Actions HW6 image](https://github.com/itzephir/hse-infra-course/actions/runs/44061782756).
- Исходный commit приложения: `5e2bd8df736045b5bce893d9a35df9c8d12a3354`.
- Тег: `ghcr.io/itzephir/hse-infra-course:sha-5e2bd8df736045b5bce893d9a35df9c8d12a3354`.
- Проверенный образ:

```text
ghcr.io/itzephir/hse-infra-course@sha256:f75f3dad2ae8bc6ded179927fc89004d55e8c19b8936314b6d8092442908cac3
```

OCI index содержит `linux/amd64` и `linux/arm64`; обе платформы прошли HTTP smoke-тест в Actions. Анонимное получение manifest из GHCR проверено отдельно. Kubelet скачал образ без `imagePullSecrets`.

## Последовательность доставки

1. Commit `5e2bd8d` опубликовал приложение и workflow, затем Actions собрал и проверил образ.
2. Commit `08d616b` зафиксировал digest в dev overlay. Argo CD самостоятельно создал Deployment и Service из Git.
3. Dev достиг `Synced / Healthy`; проверены главная страница, CSS, SVG, `/healthz`, точный image в Deployment и SHA в `/version.json`.
4. Число реплик dev вручную изменено с 1 на 2. Argo CD с `selfHeal` автоматически вернул его к 1; приложение снова `Synced`.
5. После проверки dev commit `6edcfc4` продвинул тот же digest в prod. Argo CD создал две готовые реплики; повторной сборки не было.
6. В prod повторены проверки HTTP, source SHA и image digest.

## Итоговое состояние

Кластер: профиль minikube `hw6`, Docker driver, containerd, Kubernetes `v1.37.0`, ARM64. Argo CD `v3.6.1`; все семь Pods компонентов находятся в Running/Ready. Профиль `lecture` остался остановленным, текущий kubecontext остался `lecture`; команды стенда явно указывают `--context hw6`.

```text
NAME             SYNC STATUS   HEALTH STATUS
relay-hw6-dev    Synced        Healthy
relay-hw6-prod   Synced        Healthy

dev:  Deployment relay, 1/1 available
prod: Deployment relay, 2/2 available
```

Оба `/version.json` вернули:

```json
{"name":"relay","revision":"5e2bd8df736045b5bce893d9a35df9c8d12a3354"}
```

Во время первоначальной проверки приложения Argo CD следили за `codex/hw6-gitops`; теперь родитель следит за `gitops/hw6`, а дочерние приложения закрепляют исходные commit SHA. Интерфейс Argo CD доступен по HTTPS; его страница входа проверена с доверием к конкретному локальному сертификату, без отключения проверки TLS.

## Дополнительные проверки

- Локальная сборка контейнера и HTTP smoke-тест ARM64 с файловой системой только для чтения.
- Лендинг просмотрен в браузере на desktop и при viewport `390 × 844`; переход по основной кнопке работает, мобильная компоновка читается без горизонтального переполнения.
- Действующий и два альтернативных workflow прошли `actionlint`.
- YAML и оба Kustomize overlays разобраны; shell-скрипты прошли проверку синтаксиса, ссылки Markdown проверены.

Push CD остаётся альтернативным примером из условия; на работающем стенде доставкой управляет Argo CD. Запуск альтернативных push jobs и предоставление CI kubeconfig не выполнялись.

## Доступ и повторный запуск

Пока работает [port-forward.sh](scripts/port-forward.sh): [dev](http://127.0.0.1:18080), [prod](http://127.0.0.1:18081), [Argo CD](https://127.0.0.1:18443).

Если локальные адреса перестали отвечать, повторно запустить `bash hw/06/scripts/port-forward.sh`. Команды получения начального пароля Argo CD, остановки и возобновления minikube приведены в [решении](solution.md#запуск-и-доступ). Пароли, ключи и kubeconfig в Git не добавлены.
