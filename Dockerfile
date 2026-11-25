# Misma versión de Python que el entorno local (3.13), sobre Debian 13 (trixie)
FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Solo parches de seguridad del sistema. No hace falta compilar nada: el driver
# de MySQL (PyMySQL) es Python puro y el resto de paquetes trae ruedas listas.
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# El pip de la imagen base puede traer una copia propia de urllib3 con CVEs.
ARG PIP_VERSION=26.3
RUN pip install --no-cache-dir --root-user-action=ignore "pip==${PIP_VERSION}"

WORKDIR /app

# Primero solo requirements: si no cambian, Docker reutiliza esta capa
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "-k", "gevent", "--timeout", "60", "--access-logfile", "-"]
