from flask import Flask
from flask_cors import CORS
from app.config import Config
from app.views.insumo import insumos_bp
from app.views.inventario import inventario_bp
import logging
from .json_encoder import CustomJSONEncoder

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
            "origins": ["http://localhost:3000", "http://localhost:5173"],  # Frontend común
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Registrar blueprints
    app.register_blueprint(insumos_bp)
    app.register_blueprint(inventario_bp)

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