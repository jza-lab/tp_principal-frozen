from flask import Flask
from flask_cors import CORS
from app.config import Config
import logging
from .json_encoder import CustomJSONEncoder

# Helpers de la aplicación
from app.utils.template_helpers import register_template_extensions

def _register_blueprints(app: Flask):
    """Registra todos los blueprints de la aplicación."""
    from app.views.main_routes import main_bp
    from app.views.insumo import insumos_bp
    from app.views.inventario import inventario_bp as inventario_api_bp
    from app.views.inventario_routes import inventario_view_bp
    from app.views.auth_routes import auth_bp
    from app.views.admin_dashboard_routes import admin_dashboard_bp
    from app.views.admin_usuario_routes import admin_usuario_bp
    from app.views.admin_autorizacion_routes import admin_autorizacion_bp
    from app.views.api_routes import api_bp
    from app.views.orden_produccion_routes import orden_produccion_bp
    from app.views.orden_compra_routes import orden_compra_bp
    from app.views.facial_routes import facial_bp
    from app.views.pedido_routes import orden_venta_bp
    from app.views.planificacion_routes import planificacion_bp
    from app.views.google_forms_routes import google_forms_bp
    from app.views.precios_routes import precios_bp
    from app.views.productos_routes import productos_bp
    from app.views.cliente_proveedor_routes import cliente_proveedor
    from app.views.lote_producto_routes import lote_producto_bp
    from app.views.reservas_routes import reservas_bp
    from app.views.admin_tarea_routes import admin_tasks_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(insumos_bp)
    app.register_blueprint(inventario_api_bp)
    app.register_blueprint(inventario_view_bp)
    app.register_blueprint(orden_produccion_bp)
    app.register_blueprint(orden_compra_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_dashboard_bp)
    app.register_blueprint(admin_usuario_bp)
    app.register_blueprint(admin_autorizacion_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(facial_bp, url_prefix='/totem')
    app.register_blueprint(orden_venta_bp)
    app.register_blueprint(planificacion_bp)
    app.register_blueprint(google_forms_bp)
    app.register_blueprint(precios_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(cliente_proveedor)
    app.register_blueprint(lote_producto_bp)
    app.register_blueprint(reservas_bp)
    app.register_blueprint(admin_tasks_bp)

def _register_error_handlers(app: Flask):
    """Registra los manejadores de errores globales."""
    @app.errorhandler(404)
    def not_found(error):
        return {'success': False, 'error': 'Endpoint no encontrado'}, 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return {'success': False, 'error': 'Método no permitido'}, 405

    @app.errorhandler(500)
    def internal_error(error):
        return {'success': False, 'error': 'Error interno del servidor'}, 500

def create_app() -> Flask:
    """
    Factory para crear y configurar la aplicación Flask.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json = CustomJSONEncoder(app)

    CORS(app, resources={r"/api/*": {"origins": "*"}}) 

    _register_blueprints(app)
    _register_error_handlers(app)
    register_template_extensions(app)

    return app
