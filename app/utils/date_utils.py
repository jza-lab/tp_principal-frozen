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