#!/bin/sh
# Aplica las migraciones al arrancar el contenedor web.
#
# En una BD NUEVA hay migraciones que repiten cambios ya hechos por otras, así
# que se marcan como aplicadas sin ejecutarlas (--fake):
#   - Rama antigua 0002_transaccionpendiente -> 0006_registro_transacciones_tipo_pago:
#     sus tablas ya las crean 0001_initial y 0002_remove_registro_transacciones_...
#   - 0019_deuda_dia_corte_deuda_dia_pago_and_more: sus 3 columnas ya las
#     agregan 0014 y 0015.
# Una BD que ya tiene 0001_initial aplicado solo corre `migrate` normal.
set -e

if ! python manage.py showmigrations finanzas | grep -q '\[X\] 0001_initial'; then
    echo "BD nueva: aplicando migraciones y marcando las duplicadas como aplicadas"
    python manage.py migrate finanzas 0015_deuda_dia_corte_deuda_dia_pago --noinput
    python manage.py migrate finanzas 0006_registro_transacciones_tipo_pago --fake --noinput
    python manage.py migrate finanzas 0018_deuda_dia_corte_deuda_dia_pago_and_more --noinput
    python manage.py migrate finanzas 0019_deuda_dia_corte_deuda_dia_pago_and_more --fake --noinput
fi

python manage.py migrate --noinput
