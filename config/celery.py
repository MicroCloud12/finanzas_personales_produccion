# config/celery.py
import os
from celery import Celery
from celery.schedules import crontab

# Establece el módulo de configuración de Django por defecto para el programa 'celery'.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Usa una cadena aquí para que el worker no tenga que serializar
# el objeto de configuración a los procesos hijos.
# El namespace='CELERY' significa que todas las claves de configuración de Celery
# deben tener un prefijo `CELERY_`.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carga automáticamente las tareas desde todos los archivos 'tasks.py' de las apps registradas.
app.autodiscover_tasks()


# Programación de tareas periódicas
app.conf.beat_schedule = {
    'update-profits-monthly': {
        'task': 'django.core.management.call_command',
        'schedule': crontab(day_of_month=1, hour=2),
        'args': ('update_monthly_profits',),
    },
}