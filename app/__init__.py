from flask import Flask, redirect, url_for, flash, session, request 
from flask_cors import CORS
from flask_jwt_extended import JWTManager, unset_jwt_cookies, get_current_user
from flask_jwt_extended import JWTManager, unset_jwt_cookies, get_current_user, verify_jwt_in_request
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from app.config import Config
import logging
from .json_encoder import CustomJSONEncoder
from datetime import timedelta, datetime

from app.models.token_blacklist_model import TokenBlacklistModel
from app.models.rol import RoleModel
from app.controllers.cliente_controller import ClienteController
from app.models.reclamo import ReclamoModel
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
    Ahora es 'stateless'. Devuelve un objeto de usuario construido a partir
    de las 'claims' del propio token JWT, evitando una consulta a la base de datos.
    """
    identity = jwt_data["sub"]
    rol_codigo = jwt_data.get('rol')

    # Imprimir en consola para depuración
    print(f"--- JWT User Lookup --- ID: {identity}, Rol: {rol_codigo} ---")

    # Se reconstruye un objeto de usuario mínimo para ser compatible con el resto de la app
    # sin necesidad de consultar la base de datos.
    user_data = {
        'id': int(identity),
        'nombre': jwt_data.get('nombre'),
        'apellido': jwt_data.get('apellido'),
        'rol': rol_codigo,
        'nombre_completo': f"{jwt_data.get('nombre', '')} {jwt_data.get('apellido', '')}".strip(),
        # Reconstruimos el objeto 'roles' directamente desde el token
        'roles': {'codigo': rol_codigo, 'nombre': jwt_data.get('rol_nombre', rol_codigo)}
    }
    return SimpleNamespace(**user_data)


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
    from app.views.cliente_routes import cliente_bp
    from app.views.reclamo_routes import reclamo_bp
    from app.views.admin_reclamo_routes import admin_reclamo_bp # <-- IMPORTACIÓN DE ADMIN RECLAMO
    from app.views.admin_consulta_routes import consulta_bp
    from app.views.receta_routes import receta_bp

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
    app.register_blueprint(cliente_bp)
    app.register_blueprint(reclamo_bp)
    app.register_blueprint(admin_reclamo_bp) # <-- REGISTRO DE ADMIN RECLAMO
    app.register_blueprint(consulta_bp)
    app.register_blueprint(receta_bp)

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

def _format_datetime_filter(value, format='%d/%m/%Y %H:%M'):
    """Filtro Jinja para formatear fechas y horas."""
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    if isinstance(value, datetime):
        return value.strftime(format)
    return value

def _formato_moneda_filter(value):
    """Filtro Jinja para formatear un número como moneda."""
    if value is None:
        return "$ 0.00"
    try:
        # Formatea con separador de miles y dos decimales
        return f"$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return value

def _has_permission_filter(accion: str) -> bool:
    """
    Verifica si el rol del usuario actual (almacenado en la sesión de Flask)
    tiene el permiso para realizar una acción específica.
    """
    try:
        # Usamos get_current_user(), que devuelve el usuario si está logueado, o None si no lo está.
        # Esto funciona gracias a nuestro user_lookup_loader.
        user = get_current_user()
        if not user:
            return False
        
        # El user_lookup_loader ya nos da un objeto con el rol.
        rol_usuario = getattr(user, 'rol', None)
        if not rol_usuario:
            return False
        
        return RoleModel.check_permission(rol_usuario, accion)
    except RuntimeError: # Capturamos específicamente el error de "fuera de contexto"
        # En caso de cualquier error (ej: fuera de un contexto de request), denegar permiso.
        return False

def create_app() -> Flask:
    """
    Factory para crear y configurar la aplicación Flask.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False  
    app.json = CustomJSONEncoder(app)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    csrf.init_app(app)
    jwt.init_app(app)

    @app.context_processor
    def inject_globals():
        return dict(timedelta=timedelta)

    @app.context_processor
    def inject_csrf_form():
        return dict(csrf_form=FlaskForm())

    @app.context_processor
    def inject_pending_client_count():
        conteo = 0
        current_user = get_current_user()
        if current_user and hasattr(current_user, 'rol') and current_user.rol in ['DEV', 'GERENTE']:
            cliente_controller = ClienteController()
            _, status = cliente_controller.obtener_conteo_clientes_pendientes()
            if status == 200:
                conteo = _.get('data', {}).get('count', 0)
        return dict(pending_client_count=conteo)

    @app.context_processor
    def inject_cliente_notifications():
        """
        Inyecta el conteo de reclamos respondidos para el cliente logueado
        en todas las plantillas.
        """
        conteo = 0
        current_user = get_current_user()
        # Asumiendo que un 'cliente' tiene un rol específico, por ejemplo 'CLIENTE'
        if current_user and hasattr(current_user, 'rol') and current_user.rol == 'CLIENTE':
            try:
                cliente_id = current_user.id
                reclamo_model = ReclamoModel()
                resultado = reclamo_model.get_count_by_cliente_and_estado(cliente_id, 'respondida')
                if resultado.get('success'):
                    conteo = resultado.get('count', 0)
            except Exception as e:
                print(f"Error al inyectar conteo de reclamos: {e}")
                conteo = 0
        return dict(conteo_reclamos_respondidos=conteo)

    @app.context_processor
    def _inject_permission_map():
        """Inyecta el mapa de permisos en el contexto de la plantilla."""
        return dict(permission_map=RoleModel.get_permission_map())

    @app.context_processor
    def _inject_user_from_jwt():
        """
        Inyecta los datos del usuario desde el token JWT en el contexto de la plantilla,
        si el usuario está autenticado.
        """
        from flask_jwt_extended import get_current_user
        try:
            return dict(current_user=get_current_user())
        except RuntimeError:
            # Esto ocurre si no hay un contexto de petición JWT activo (ej. en páginas públicas).
            return dict(current_user=None)
    
    # Registrar filtros directamente en el entorno de Jinja
    app.jinja_env.filters['format_datetime'] = _format_datetime_filter
    app.jinja_env.filters['formato_moneda'] = _formato_moneda_filter
    app.jinja_env.globals['has_permission'] = _has_permission_filter
    app.jinja_env.tests['has_permission'] = _has_permission_filter
    
    _register_blueprints(app)
    _register_error_handlers(app)
    
    @app.before_request
    def before_request_loader():
        """
        Se ejecuta antes de cada petición.
        Intenta verificar si hay un token JWT en la petición (de forma opcional).
        Esto asegura que `get_current_user()` y la variable `current_user` en Jinja
        funcionen en todas las plantillas, incluso en vistas no protegidas.
        """
        # Evitar la verificación de JWT para las rutas de archivos estáticos,
        # ya que es innecesario y causa consultas a la BD por cada CSS, JS, etc.
        if request.endpoint and (request.endpoint.startswith('static') or request.blueprint == 'static'):
            return
        verify_jwt_in_request(optional=True)

    return app