# Imagen de verificación de la librería de cálculo de estadías hoteleras.
#
# Construye las dependencias de desarrollo en una etapa intermedia y ejecuta
# la suite de pruebas en una imagen final sin privilegios, sin puertos
# publicados y sin servidor: el contenedor corre pytest y propaga su código de
# salida.
#
# Contexto de build: raíz del repositorio.

# --- Etapa de compilación: dependencias de desarrollo -------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Entorno virtual para aislar las dependencias de la imagen base.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

# --- Etapa de ejecución: suite de pruebas -------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv

COPY pytest.ini /app/pytest.ini
COPY src/ /app/src/
COPY tests/ /app/tests/
COPY README.md /app/README.md

# Usuario sin privilegios: la imagen no necesita permisos elevados para correr
# las pruebas. /app se entrega con permisos de escritura para el cache de
# pytest.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "pytest", "-v"]
