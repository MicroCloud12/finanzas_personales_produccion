# finanzas/utils.py
from datetime import datetime, date

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