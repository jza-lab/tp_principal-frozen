from flask import Blueprint, jsonify, redirect, session, url_for

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Ruta raíz que limpia la sesión y redirige al login."""
    session.clear()
    return redirect(url_for('auth.login'))

@main_bp.route('/api/health')
def health_check():
    """Endpoint de health check para verificar que la API está funcionando."""
    return jsonify({
        'status': 'ok',
        'message': 'API de Trazabilidad de Insumos funcionando correctamente',
        'version': '1.0.0'
    })
