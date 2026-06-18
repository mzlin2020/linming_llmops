#!/bin/bash
# 容器统一入口：MODE 决定 API (gunicorn/flask run) 还是 celery worker。
set -e

if [[ "${MIGRATION_ENABLED}" == "true" ]]; then
  echo "[entrypoint] Running alembic upgrade ..."
  flask --app app.http.app db upgrade
  if [[ -n "${BOOTSTRAP_ACCOUNT_EMAIL}" ]]; then
    echo "[entrypoint] Seeding bootstrap account ..."
    flask --app app.http.app seed-bootstrap-account || true
  fi
  echo "[entrypoint] Seeding LLM catalog ..."
  flask --app app.http.app seed-llm-catalog || true
fi

if [[ "${MODE}" == "celery" ]]; then
  echo "[entrypoint] Starting Celery worker ..."
  exec celery -A app.http.app.celery worker \
    -P "${CELERY_POOL:-prefork}" \
    -c "${CELERY_CONCURRENCY:-5}" \
    --loglevel "${CELERY_LOG_LEVEL:-INFO}"
else
  if [[ "${FLASK_ENV}" == "development" ]]; then
    echo "[entrypoint] Starting Flask dev server ..."
    exec flask run --host "${SERVER_BIND_HOST:-0.0.0.0}" --port "${PORT:-5001}" --debug
  else
    echo "[entrypoint] Starting gunicorn ..."
    exec gunicorn \
      --config docker/gunicorn.conf.py \
      --bind "${SERVER_BIND_HOST:-0.0.0.0}:${PORT:-5001}" \
      --workers "${SERVER_WORKER_AMOUNT:-2}" \
      --worker-class "${SERVER_WORKER_CLASS:-gthread}" \
      --threads "${SERVER_THREAD_AMOUNT:-4}" \
      --timeout "${GUNICORN_TIMEOUT:-600}" \
      --preload \
      app.http.app:app
  fi
fi
