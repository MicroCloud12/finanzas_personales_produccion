# finanzas/utils.py
from decimal import Decimal
from calendar import monthrange
from .models import inversiones
from datetime import datetime, date
from collections import defaultdict


def parse_date_safely(date_str: str | None) -> date:
    """
    Convierte y valida de forma segura una cadena de texto a un objeto de fecha.
    Si la fecha parseada es de hace más de un año, la considera inválida.
    Si falla, devuelve la fecha actual.
    """
    parsed_date = None
    
    if date_str and isinstance(date_str, str):
        formats_to_try = [
            '%Y-%m-%d',  # Formato ideal (ISO)
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%Y/%m/%d',
            '%d/%m/%y',
        ]
        for fmt in formats_to_try:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                break  # Si tiene éxito, salimos del bucle
            except (ValueError, TypeError):
                continue

    # --- LÓGICA DE VALIDACIÓN MEJORADA ---
    if parsed_date:
        # Si la fecha extraída es de hace más de 365 días, es muy probable que
        # sea un error de la IA. Es más seguro usar la fecha actual.
        if (datetime.now().date() - parsed_date).days > 365:
            print(f"ADVERTENCIA: La fecha extraída '{parsed_date}' es muy antigua y fue descartada. Se usará la fecha actual.")
            return datetime.now().date()
        else:
            # La fecha es razonable y se devuelve
            return parsed_date

    # Fallback final si no se pudo parsear o la cadena era inválida
    if date_str:
        print(f"ADVERTENCIA: La cadena de fecha '{date_str}' no pudo ser procesada. Se usará la fecha actual.")
    return datetime.now().date()

def calculate_monthly_profit(user, price_service=None):
    from .services import StockPriceService
    """Calcula la ganancia mensual no realizada de las inversiones de un usuario."""
    if price_service is None:
       price_service = StockPriceService()

    profits = defaultdict(Decimal)
    today = datetime.now().date()

    for inv in inversiones.objects.filter(propietario=user):
        if not inv.emisora_ticker:
            continue

        year = inv.fecha_compra.year
        month = inv.fecha_compra.month

        while (year, month) <= (today.year, today.month):
            last_day = monthrange(year, month)[1]
            date_obj = date(year, month, last_day)
            closing = price_service.get_closing_price_for_date(inv.emisora_ticker, date_obj)
           
            #valor_actual_mercado = closing  * inv.cantidad_titulos
            
            
            #total_inversiones = inversiones_del_mes.aggregate(total=Sum('costo_total_adquisicion'))['total'] or Decimal('0.00')
            #total_valor_actual = inversiones_del_mes.aggregate(total=Sum('valor_actual_mercado'))['total'] or Decimal('0.00')

            if closing is not None:
                profit = sum((Decimal(str(closing)) - inv.precio_compra_titulo) * inv.cantidad_titulos)['total'] or Decimal('0.00')
                profits[f"{year}-{month:02d}"] += profit

            month += 1
            if month > 12:
                month = 1
                year += 1

    # Ordenamos por fecha para devolver una lista coherente
    return dict(sorted(profits.items()))