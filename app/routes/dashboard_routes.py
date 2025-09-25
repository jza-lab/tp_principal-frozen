from flask import Blueprint, render_template, session, redirect, url_for, flash
from app.services.asistencia_service import AsistenciaService
from app.repositories.asistencia_repository import AsistenciaRepository

dashboard_bp = Blueprint('dashboard', __name__)

# Inyección de dependencias
asistencia_repo = AsistenciaRepository()
asistencia_service = AsistenciaService(asistencia_repo)

@dashboard_bp.route('/dashboard')
def index():
    """Muestra el dashboard principal."""
    usuario_id = session.get('usuario_id', None)
    if not usuario_id:
        flash('Por favor, inicie sesión para continuar')
        return redirect(url_for('usuario.login'))
    
    # Aquí puedes agregar la lógica para obtener las estadísticas.
    # Por ahora, las dejaremos como valores por defecto.
    estadisticas = {
        'ordenes_en_proceso': 0,
        'ordenes_planificadas': 0,
        'alertas_stock_bajo': 0,
    }
    
    alertas = [] # Lista de alertas vacía por ahora

    return render_template(
        'dashboard/index.html',
        estadisticas=estadisticas,
        alertas=alertas,
        #estado_asistencia=estado_asistencia  #implementar con lo de los totems
    )
