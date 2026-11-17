FROM nginxinc/nginx-unprivileged:1.28-alpine@sha256:7377697a821c131a924a7105fafbe7414db4e9fcc77a6f08f776f33f141ec3f8
ARG SOURCE_REVISION=local
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 public/ /srv/site/
RUN printf '{"name":"relay","revision":"%s"}\n' "$SOURCE_REVISION" > /srv/site/version.json
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
