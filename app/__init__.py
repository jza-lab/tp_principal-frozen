from flask import Flask, redirect, url_for, session, flash
from flask_cors import CORS
from app.config import Config
from app.routes.usuario_routes import usuario_bp
from app.routes.insumo_routes import insumo_bp
from app.routes.asistencia_routes import asistencia_bp
from app.routes.dashboard_routes import dashboard_bp
from app.routes.orden_produccion_routes import orden_produccion_bp
from app.routes.reportes_routes import reportes_bp      
from app.routes.redirects import redirect_bp
import logging
from .json_encoder import CustomJSONEncoder

def create_app():
    """Factory para crear la aplicación Flask"""

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    app.config['SECRET_KEY'] = 'a_very_secret_key'


     # ✅ Configurar el encoder personalizado para Flask 2.3+
    app.json = CustomJSONEncoder(app)

    # Configurar CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://localhost:5173"],  # Frontend común
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Registrar blueprints
    app.register_blueprint(usuario_bp)
    app.register_blueprint(insumo_bp)
    app.register_blueprint(asistencia_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(orden_produccion_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(redirect_bp)

    # --- DEV-ONLY: RUTA PARA SALTAR EL LOGIN ---
    @app.route('/dev-login')
    def dev_login():
        """Ruta temporal para desarrollo que simula un inicio de sesión."""
        
        session['usuario_id'] = 999  # ID de usuario de prueba
        session['usuario_rol'] = 'admin'
        session['usuario_nombre'] = 'Usuario de Prueba'
        flash('Inicio de sesión de desarrollo exitoso.', 'info')
        return redirect(url_for('dashboard.index'))

    # Ruta raíz para redirigir al login (o al dev-login)
    @app.route('/')
    def index():
        session.clear()
        return redirect(url_for('usuario.login'))

    # Ruta de health check
    @app.route('/api/health')
    def health_check():
        return {
            'status': 'ok',
            'message': 'API de Trazabilidad de Insumos funcionando correctamente',
            'version': '1.0.0'
        }

    # Manejo de errores globales
    @app.errorhandler(404)
    def not_found(error):
        return {
            'success': False,
            'error': 'Endpoint no encontrado',
            'message': 'Verifique la URL y el método HTTP'
        }, 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return {
            'success': False,
            'error': 'Método no permitido',
            'message': 'Verifique el método HTTP de la solicitud'
        }, 405

    @app.errorhandler(500)
    def internal_error(error):
        return {
            'success': False,
            'error': 'Error interno del servidor',
            'message': 'Contacte al administrador del sistema'
        }, 500

    return app