from flask import Blueprint, jsonify
from app.controllers.session_controller import SessionController

session_bp = Blueprint('session', __name__, url_prefix='/sessions')
session_controller = SessionController()

@session_bp.route('/close-expired', methods=['POST'])
def close_expired_sessions():
    """
    Endpoint para cerrar manualmente las sesiones expiradas.
    """
    result = session_controller.close_expired_sessions()
    if result.get('success'):
        return jsonify(result), 200
    else:
        return jsonify(result), 500
