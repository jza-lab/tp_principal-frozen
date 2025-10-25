from flask import Flask, redirect, url_for, flash
from flask_cors import CORS
from flask_jwt_extended import JWTManager, unset_jwt_cookies
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from app.config import Config
import logging
from .json_encoder import CustomJSONEncoder

# Helpers de la aplicación
from app.utils.template_helpers import register_template_extensions
from app.models.token_blacklist_model import TokenBlacklistModel
from app.controllers.usuario_controller import UsuarioController
from app.models.usuario import UsuarioModel
from types import SimpleNamespace

jwt = JWTManager()
csrf = CSRFProtect()

@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return TokenBlacklistModel.is_blacklisted(jti)


@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    """
    Esta función se llama cada vez que se protege una ruta con jwt_required.
    Devuelve el objeto de usuario basado en el 'sub' del token JWT,
    y añade los claims adicionales (rol, permisos) al objeto.
    """
    identity = jwt_data["sub"]
    user_id = int(identity)

    # El controlador de usuario ya tiene una lógica para preparar los datos de sesión.
    # Reutilizamos esa lógica para asegurar consistencia.
    user_controller = UsuarioController()
    user_result = user_controller.model.find_by_id(user_id)

    if user_result.get('success'):
        user_data = user_result['data']
        # Añadimos los permisos y otros datos del token directamente al objeto.
        # Esto asegura que `current_user` tenga todo lo necesario en las plantillas.
        user_data['permisos'] = jwt_data.get('permisos', {})
        user_data['rol'] = jwt_data.get('rol')
        user_data['nombre_completo'] = f"{user_data.get('nombre', '')} {user_data.get('apellido', '')}".strip()
        
        # Usamos SimpleNamespace para un acceso más fácil tipo objeto en las plantillas
        return SimpleNamespace(**user_data)

    return None


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """
    Se ejecuta cuando se accede a una ruta protegida con un token expirado.
    Redirige al usuario a la página de login.
    """
    response = redirect(url_for('auth.login'))
    unset_jwt_cookies(response)
    flash('Tu sesión ha expirado. Por favor, inicia sesión de nuevo.', 'warning')
    return response

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
    from app.views.alertas_routes import alertas_bp
    from app.views.public_routes import public_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(public_bp)
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
    app.register_blueprint(alertas_bp)

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
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False  # Dejar que Flask-WTF maneje CSRF
    app.json = CustomJSONEncoder(app)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    csrf.init_app(app)
    jwt.init_app(app)

    @app.context_processor
    def inject_csrf_form():
        return dict(csrf_form=FlaskForm())

    _register_blueprints(app)
    _register_error_handlers(app)
    register_template_extensions(app)

    return app