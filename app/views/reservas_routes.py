from flask import Blueprint, render_template, flash
from app.controllers.reservas_controller import ReservasController
from app.utils.decorators import permission_required

reservas_bp = Blueprint('reservas', __name__, url_prefix='/reservas')

@reservas_bp.route('/')
@permission_required(accion='consultar_trazabilidad_completa')
def listar():
    """Muestra la vista unificada de trazabilidad de reservas."""
    controller = ReservasController()
    response, status_code = controller.obtener_trazabilidad_reservas()

    reservas = []
    if response.get('success'):
        reservas = response.get('data', [])
    else:
        flash(response.get('error', 'No se pudo cargar la trazabilidad de reservas.'), 'error')

    return render_template('reservas/listar.html', reservas=reservas)
