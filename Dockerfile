# Usa una imagen oficial de Python como base
FROM python:3.11-slim-bookworm


# Evita que Python escriba archivos .pyc y guarde la salida en un búfer
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# --- IMPORTANTE: Instalar dependencias del sistema para mysqlclient ---
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

RUN chmod +x /app/cron_job.sh

# Copia e instala las dependencias de Python
COPY requirements.txt .
RUN pip install gunicorn whitenoise[brotli]
RUN pip install -r requirements.txt

# Copia el código de la aplicación
COPY . .

# Ejecuta collectstatic
RUN python manage.py collectstatic --noinput

# Expone el puerto 8000
EXPOSE 8000

# Comando para ejecutar la aplicación
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]