from flask import Flask
from flask_cors import CORS
from app.config import Config
import logging
<<<<<<< HEAD
from .json_encoder import CustomJSONEncoder
<<<<<<< HEAD

# --- Blueprints ---
from app.views.insumo import insumos_bp
from app.views.inventario import inventario_bp
from app.views.auth_routes import auth_bp
from flask import Flask
from flask_cors import CORS
from app.config import Config
import logging
from .json_encoder import CustomJSONEncoder
=======
from app.json_encoder import CustomJSONEncoder
>>>>>>> d55bac8 (manejo de rutas fix)

# --- Blueprints ---
from app.views.insumo import insumos_bp
from app.views.inventario import inventario_bp
from app.views.auth_routes import auth_bp
from app.views.admin_usuario_routes import admin_usuario_bp
from app.views.facial_routes import facial_bp
from app.views.orden_compra_routes import orden_compra_bp  # ✅ Tu nuevo blueprint

def create_app():
    """Factory para crear la aplicación Flask"""

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app = Flask(__name__)
    app.config.from_object(Config)

    # ✅ Configurar el encoder personalizado para Flask 2.3+
    app.json = CustomJSONEncoder(app)

    # Configurar CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://localhost:5173"],
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"]
        },
        r"/auth/*": {
            "origins": ["http://localhost:3000", "http://localhost:5173"],
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"]
        },
        r"/ordenes-compra/*": {
            "origins": ["http://localhost:3000", "http://localhost:5173"],
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # --- Registrar blueprints ---
    app.register_blueprint(insumos_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_usuario_bp)
    app.register_blueprint(facial_bp, url_prefix='/auth')
    app.register_blueprint(orden_compra_bp)  # ✅ Tu nuevo blueprint

    # Ruta de health check
    @app.route('/api/health')
    def health_check():
        return {
            'status': 'ok',
            'message': 'API de Trazabilidad de Insumos funcionando correctamente',
            'version': '1.0.0'
        }

    # Ruta de health check específica para auth
    @app.route('/auth/health')
    def auth_health_check():
        return {
            'status': 'ok',
            'message': 'Módulo de Autenticación funcionando correctamente',
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