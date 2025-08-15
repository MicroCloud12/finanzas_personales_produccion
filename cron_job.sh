#!/bin/sh

# Escribe las variables de entorno en un archivo que cron pueda leer
printenv | grep -v "no_proxy" > /etc/environment

echo "Contenedor de Cron iniciado. Tareas programadas:"

# Añade las tareas al crontab
echo "0 2 * * * python3 /app/manage.py update_prices >> /var/log/cron.log 2>&1" > /etc/crontabs/root
echo "0 3 1 * * python3 /app/manage.py update_monthly_profits >> /var/log/cron.log 2>&1" >> /etc/crontabs/root

# Muestra las tareas que se acaban de programar
cat /etc/crontabs/root

# Inicia el demonio de cron EN PRIMER PLANO.
# Esto es más estable y es la forma recomendada de ejecutar cron en Docker.
crond -f -l 8