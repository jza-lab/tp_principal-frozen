from datetime import datetime
import pytz

def get_now_in_argentina() -> datetime:
    """
    Devuelve el objeto datetime actual para la zona horaria de Argentina.
    """
    argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
    return datetime.now(argentina_tz)