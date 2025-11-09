from datetime import datetime
import pytz

def get_now_in_argentina() -> datetime:
    """
    Devuelve el objeto datetime actual para la zona horaria de Argentina.
    """
    argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
    return datetime.now(argentina_tz)

def get_today_utc3_range():
    """
    Devuelve una tupla con el inicio y el fin del día actual en la zona horaria de Argentina.
    """
    today = get_now_in_argentina().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    return start_of_day, end_of_day

def format_datetime_to_arg(datetime_str: str) -> str:
    """
    Convierte un string de fecha y hora (potencialmente UTC) a la zona horaria de Argentina
    y lo formatea.
    """
    if not datetime_str:
        return ""
    try:
        # Asume que el string es un formato ISO 8601 que puede venir de la BD
        utc_dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        
        # Si no tiene timezone, asumimos UTC
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
            
        argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
        arg_dt = utc_dt.astimezone(argentina_tz)
        
        return arg_dt.strftime('%d/%m/%Y %H:%M:%S')
    except (ValueError, TypeError):
        # Si el formato no es válido, devolvemos el string original
        return datetime_str