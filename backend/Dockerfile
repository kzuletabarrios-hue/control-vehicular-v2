# Build explícito del backend para Railway.
# Railpack (el builder automático) empezó a fallar en el paso "prepare"
# desde la v0.40.1 (2026-09-30) sin cambios en el proyecto; con este
# Dockerfile Railway ya no depende de esa detección automática.
# Replica lo que hacía Railpack: Python 3.12, pip install y uvicorn en $PORT.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Forma shell para que se expanda $PORT, que asigna Railway.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
