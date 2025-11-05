
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

def setup_template_helpers(app):
    """Registra los helpers con la aplicación Flask."""
    @app.context_processor
    def inject_helpers():
        return dict(format_product_units=format_product_units)
