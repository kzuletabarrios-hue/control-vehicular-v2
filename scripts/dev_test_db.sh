#!/usr/bin/env bash
# ================================================================
# Entorno de pruebas LOCAL (nunca producción) para control-vehicular-v2.
#
# Por qué existe este script en vez de solo `supabase start`:
# esta máquina de desarrollo no tiene Docker Desktop ni WSL2
# instalados, y `supabase start` los requiere. En su lugar, este
# script levanta un Postgres 18 standalone (mismos binarios de
# PostgreSQL ya instalados en la máquina), aislado en .devstack/,
# y usa `supabase db reset --db-url` para aplicar
# supabase/migrations/ + supabase/seed.sql contra él. No emula
# GoTrue/PostgREST/Storage/Studio -- el backend de esta app se
# conecta siempre directo a Postgres (SQLAlchemy), nunca a la API
# REST de Supabase, así que no hace falta para testear el backend.
#
# Si más adelante se instala Docker Desktop, se puede migrar a
# `supabase start` real (ver notas en backend/.env.test).
#
# Uso:
#   bash scripts/dev_test_db.sh up      # crea el cluster si no existe y lo arranca
#   bash scripts/dev_test_db.sh reset   # recrea la BD de pruebas desde cero y aplica
#                                       # las 46 migraciones + seed.sql (destructivo,
#                                       # SOLO afecta la BD local de pruebas)
#   bash scripts/dev_test_db.sh stop    # detiene el Postgres local de pruebas
#   bash scripts/dev_test_db.sh status  # muestra si está corriendo
#
# Requiere: PostgreSQL instalado en
#   "C:\Program Files\PostgreSQL\18\bin" (ajustar PG_BIN si tu
#   instalación está en otra ruta/versión), y Node (para `npx supabase`).
# ================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PG_BIN="${PG_BIN:-/c/Program Files/PostgreSQL/18/bin}"
PGDATA_DIR="$REPO_ROOT/.devstack/pgdata"
PG_PORT="${PG_TEST_PORT:-55432}"
PG_HOST="127.0.0.1"
PG_SUPERUSER="postgres"
PG_SUPERPASS="postgres"
TEST_DB="control_vehicular_test"
DB_URL="postgresql://${PG_SUPERUSER}:${PG_SUPERPASS}@${PG_HOST}:${PG_PORT}/${TEST_DB}?sslmode=disable"

export PGPASSWORD="$PG_SUPERPASS"

_pg_ctl() { "$PG_BIN/pg_ctl.exe" "$@"; }
_psql()   { "$PG_BIN/psql.exe" -h "$PG_HOST" -p "$PG_PORT" -U "$PG_SUPERUSER" "$@"; }

cmd_up() {
  if [ ! -f "$PGDATA_DIR/PG_VERSION" ]; then
    echo "==> Inicializando cluster local en $PGDATA_DIR ..."
    mkdir -p "$REPO_ROOT/.devstack"
    printf '%s' "$PG_SUPERPASS" > "$REPO_ROOT/.devstack/.pwfile.tmp"
    "$PG_BIN/initdb.exe" -D "$PGDATA_DIR" -U "$PG_SUPERUSER" \
      --pwfile="$REPO_ROOT/.devstack/.pwfile.tmp" --auth=scram-sha-256 -E UTF8
    rm -f "$REPO_ROOT/.devstack/.pwfile.tmp"
    # Puerto no-default para no chocar con un Postgres local ya instalado.
    sed -i "s/^#port = 5432.*/port = $PG_PORT/" "$PGDATA_DIR/postgresql.conf"
  fi
  if ! _pg_ctl -D "$PGDATA_DIR" status >/dev/null 2>&1; then
    echo "==> Arrancando Postgres local de pruebas en el puerto $PG_PORT ..."
    _pg_ctl -D "$PGDATA_DIR" -l "$REPO_ROOT/.devstack/pg.log" -o "-h $PG_HOST" start
  else
    echo "==> Ya estaba corriendo."
  fi
}

cmd_stop() {
  _pg_ctl -D "$PGDATA_DIR" stop -m fast || true
}

cmd_status() {
  _pg_ctl -D "$PGDATA_DIR" status
}

cmd_reset() {
  cmd_up
  echo "==> Recreando base de datos '$TEST_DB' desde cero ..."
  "$PG_BIN/dropdb.exe" -h "$PG_HOST" -p "$PG_PORT" -U "$PG_SUPERUSER" --if-exists "$TEST_DB"
  "$PG_BIN/createdb.exe" -h "$PG_HOST" -p "$PG_PORT" -U "$PG_SUPERUSER" "$TEST_DB"
  echo "==> Aplicando supabase/migrations/ + supabase/seed.sql ..."
  npx supabase db reset --db-url "$DB_URL" --yes
  echo "==> Listo. DATABASE_URL de pruebas:"
  echo "    $DB_URL"
  echo "    (ya está en backend/.env.test)"
}

case "${1:-}" in
  up)     cmd_up ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  reset)  cmd_reset ;;
  *)
    echo "Uso: $0 {up|reset|stop|status}" >&2
    exit 1
    ;;
esac
