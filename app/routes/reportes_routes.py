from flask import Blueprint, render_template

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

@reportes_bp.route('/produccion')
def produccion():
    """
    Muestra el reporte de producción.
    NOTE: Esta es una implementación placeholder.
    """
    return render_template('reportes/produccion.html')

@reportes_bp.route('/inventario')
def inventario():
    """
    Muestra el reporte de inventario/stock.
    NOTE: Esta es una implementación placeholder.
    """
    return render_template('reportes/stock.html')

@reportes_bp.route('/trazabilidad')
def trazabilidad():
    """
    Muestra el reporte de trazabilidad.
    NOTE: Esta es una implementación placeholder.
    """
    return render_template('reportes/trazabilidad.html')
