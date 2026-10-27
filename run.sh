#!/usr/bin/env bash
# Script de arranque y verificación de la librería de costos de estadías
# hoteleras.
#
# El entregable es una librería pura: no hay servidor, ni puertos publicados, ni
# base de datos, ni variables de entorno. "Arrancar" el proyecto significa
# ejecutar su suite de pruebas, que es la verificación reproducible del
# contrato público (nights, nightly_rate, stay_total).
#
# Uso:
#   ./run.sh            # entorno local: crea .venv, instala las dependencias
#                       # de desarrollo y ejecuta la suite con pytest
#   ./run.sh --docker   # contenedor: construye la imagen y corre la suite
#   ./run.sh --help     # muestra esta ayuda

set -euo pipefail

RAIZ="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"

MODO="host"

mostrar_ayuda() {
  cat <<'AYUDA'
Script de arranque y verificación de la librería de costos de estadías.

Uso:
  ./run.sh            Ejecuta la suite en un entorno virtual local (.venv).
  ./run.sh --docker   Construye la imagen y ejecuta la suite en el contenedor.
  ./run.sh --help     Muestra esta ayuda.
AYUDA
}

ejecutar_host() {
  local VENV="${RAIZ}/.venv"

  if [ ! -x "${VENV}/bin/python" ]; then
    echo "==> Creando el entorno virtual .venv"
    python3 -m venv "${VENV}"
  fi

  echo "==> Instalando las dependencias de desarrollo (requirements-dev.txt)"
  "${VENV}/bin/python" -m pip install --quiet -r requirements-dev.txt

  echo "==> Ejecutando la suite de pruebas"
  PYTHONPATH="${RAIZ}" "${VENV}/bin/python" -m pytest -v
}

# Detecta el cliente de Docker Compose v2: el plugin 'docker compose' o el
# binario autónomo 'docker-compose'.
detectar_compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    echo "docker-compose"
    return 0
  fi
  return 1
}

ejecutar_docker() {
  local compose
  if ! compose="$(detectar_compose)"; then
    echo "ERROR: se requiere Docker Compose v2 ('docker compose' o 'docker-compose')." >&2
    exit 1
  fi

  echo "==> Eliminando el estado previo"
  ${compose} down -v 2>/dev/null || true

  echo "==> Construyendo la imagen"
  ${compose} build

  echo "==> Ejecutando la suite en el contenedor"
  ${compose} up --abort-on-container-exit
}

case "${1:-}" in
  ""|--host)
    ejecutar_host
    ;;
  --docker)
    ejecutar_docker
    ;;
  -h|--help)
    mostrar_ayuda
    ;;
  *)
    echo "ERROR: argumento desconocido '${1}' (usar --help)." >&2
    exit 2
    ;;
esac
