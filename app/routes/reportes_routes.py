from flask import Blueprint, render_template, session, url_for, redirect, flash

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

@reportes_bp.route('/produccion')
def produccion():
    usuario_id = session.get('usuario_id', None)
    if not usuario_id:
        flash('Por favor, inicie sesión para continuar')
        return redirect(url_for('usuario.login'))
    """
    Muestra el reporte de producción.
    NOTE: Esta es una implementación placeholder.
    """
    return render_template('reportes/produccion.html')

@reportes_bp.route('/inventario')
def inventario():
    usuario_id = session.get('usuario_id', None)
    if not usuario_id:
        flash('Por favor, inicie sesión para continuar')
        return redirect(url_for('usuario.login'))
    """
    Muestra el reporte de inventario/stock.
    NOTE: Esta es una implementación placeholder.
    """
    return render_template('reportes/stock.html')

@reportes_bp.route('/trazabilidad')
def trazabilidad():
    usuario_id = session.get('usuario_id', None)
    if not usuario_id:
        flash('Por favor, inicie sesión para continuar')
        return redirect(url_for('usuario.login'))
    """
    Muestra el reporte de trazabilidad.
    NOTE: Esta es una implementación placeholder.
    """
    return render_template('reportes/trazabilidad.html')
