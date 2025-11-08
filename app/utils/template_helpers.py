from datetime import datetime
import pytz

def format_product_units(producto):
    """
    Formatea la unidad de medida de un producto para mostrarla de forma estandarizada.
    Ejemplos:
    - unidad_medida='Paquete', unidades_por_paquete=12 -> 'Paquete (x12u)'
    - unidad_medida='Kg' -> 'Kg'
    - unidad_medida='Unidad' -> 'Unidad'
    """
    if not isinstance(producto, dict):
        return ""

    unidad = producto.get('unidad_medida', '')
    unidades_paquete = producto.get('unidades_por_paquete')

    if unidad and "Paquete" in unidad and unidades_paquete and unidades_paquete > 1:
        return f"Paquete (x{unidades_paquete}u)"
    
    # Manejar caso como paquete(x1kg)
    peso_valor = producto.get('peso_por_paquete_valor')
    peso_unidad = producto.get('peso_por_paquete_unidad')
    if unidad and "Paquete" in unidad and peso_valor and peso_unidad:
        return f"Paquete (x{peso_valor}{peso_unidad})"

    return unidad if unidad else ""

def format_datetime_art(value, format='%d/%m/%Y %H:%M:%S'):
    """
    Filtro Jinja para convertir una fecha UTC a la zona horaria de Argentina (ART).
    """
    if value is None:
        return ""
    
    utc_timezone = pytz.utc
    art_timezone = pytz.timezone('America/Argentina/Buenos_Aires')

    if isinstance(value, str):
        try:
            # Asumir que el string es ISO 8601 y está en UTC
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value # Devolver el string original si no se puede parsear

    # Asegurarse de que la fecha tenga información de zona horaria (asumir UTC si no tiene)
    if value.tzinfo is None:
        value = utc_timezone.localize(value)

    # Convertir a la zona horaria de Argentina
    art_datetime = value.astimezone(art_timezone)
    
    return art_datetime.strftime(format)


def format_time_filter(value):
    """Filtro para formatear HH:MM:SS a HH:MM."""
    if isinstance(value, str) and len(value.split(':')) == 3:
        return ':'.join(value.split(':')[:2])
    return value

def setup_template_helpers(app):
    """Registra los helpers con la aplicación Flask."""
    @app.context_processor
    def inject_helpers():
        return dict(
            format_product_units=format_product_units
        )
