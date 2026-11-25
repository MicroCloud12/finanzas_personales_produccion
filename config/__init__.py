# config/__init__.py

# Driver de MySQL: PyMySQL (Python puro) en lugar de mysqlclient. No necesita
# compilar ni la librería de MariaDB del sistema, y coopera con gevent.
# Debe ir antes de que Django cargue el backend de base de datos.
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:
    # Sin PyMySQL instalado (p. ej. un entorno local viejo), Django usa mysqlclient.
    pass

from .celery import app as celery_app

__all__ = ('celery_app',)
