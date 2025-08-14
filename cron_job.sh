#!/bin/sh

# Directorio de logs para asegurarnos de que existe
mkdir -p /var/log/cron
touch /var/log/cron.log

# Inicia el demonio de cron en segundo plano
cron

# Contenido del crontab (el programador de tareas)
# Usamos "echo -e" para permitir múltiples líneas
echo -e "
# Tarea 1: Actualizar precios de activos (se ejecuta todos los días a las 2 AM)
0 2 * * * python /app/manage.py update_prices >> /var/log/cron.log 2>&1

# Tarea 2: Calcular ganancias mensuales (se ejecuta el primer día de cada mes a las 3 AM)
0 3 1 * * python /app/manage.py update_monthly_profits >> /var/log/cron.log 2>&1

" > /etc/crontabs/root  # Escribe ambas líneas en el archivo de configuración de cron

# Mensaje para saber que el script se inició
echo "Contenedor de Cron iniciado. Tareas programadas:"
cat /etc/crontabs/root

# Mantiene el contenedor corriendo para que cron pueda seguir trabajando
# y muestra los logs en tiempo real para facilitar la depuración.
tail -f /var/log/cron.log