from flask import Blueprint, jsonify
from app.controllers.usuario_controller import UsuarioController

admin_tasks_bp = Blueprint('admin_tasks', __name__, url_prefix='/admin-tasks')

@admin_tasks_bp.route('/close-expired-totem-sessions', methods=['POST'])
def close_expired_totem_sessions():
    """
    Endpoint para cerrar manualmente las sesiones de tótem expiradas.
    Ideal para ser llamado por un Cron Job.
    """
    usuario_controller = UsuarioController()
    result = usuario_controller.cerrar_sesiones_expiradas_totem()
    if result.get('success'):
        return jsonify(result), 200
    else:
        return jsonify(result), 500
