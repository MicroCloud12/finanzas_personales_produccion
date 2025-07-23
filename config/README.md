# Finanzas Personales

Este proyecto utiliza Celery para procesar tareas en segundo plano.

## Ganancias mensuales

La gestión de ganancias mensuales se realiza con el comando `update_monthly_profits`.

### Ejecución automática

Celery Beat se ha configurado en `config/celery.py` para ejecutar dicho comando el primer día de cada mes a las 02:00:

```python
app.conf.beat_schedule = {
    'update-profits-monthly': {
        'task': 'django.core.management.call_command',
        'schedule': crontab(day_of_month=1, hour=2),
        'args': ('update_monthly_profits',),
    },
}
```

Para activar esta programación basta con iniciar Celery con Beat:

```bash
celery -A config worker -B
```

### Ejecución manual

También puedes lanzar la actualización manualmente cuando lo necesites:

```bash
python manage.py update_monthly_profits
```