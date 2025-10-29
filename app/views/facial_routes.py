from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    redirect,
    url_for
)
from flask_jwt_extended import get_jti, jwt_required
from app.controllers.facial_controller import FacialController
from app.utils.decorators import permission_required
import logging

logger = logging.getLogger(__name__)

# Crear blueprint de autenticación facial
facial_bp = Blueprint("facial", __name__, template_folder="templates")

@facial_bp.route("/")
def index():
    """Página principal - redirigir al tótem"""
    return render_template("totem/login_totem.html")


@facial_bp.route("/index")
def facial_index():
    """Alias para facial.index"""
    return redirect(url_for("facial.login_totem"))


@facial_bp.route("/process_access", methods=["POST"])
def process_access():
    """Punto de entrada único para el tótem."""
    facial_controller = FacialController()
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"success": False, "message": "No se recibió imagen"})
    resultado = facial_controller.procesar_acceso_unificado_totem(data["image"])
    if resultado.get("success"):
        tipo_acceso = resultado.get("tipo_acceso")
        return jsonify(
            {
                "success": True,
                "message": resultado.get("message"),
                "tipo_acceso": tipo_acceso,
                "redirect_url": url_for("facial.panel_totem"),
            }
        )
    else:
        return jsonify(
            {
                "success": False,
                "message": resultado.get("message", "Error desconocido."),
            }
        )


@facial_bp.route("/manual_access", methods=["POST"])
def manual_access():
    """Punto de entrada para el acceso manual desde el tótem."""
    facial_controller = FacialController()
    data = request.get_json()
    legajo = data.get("legajo")
    password = data.get("password")
    if not legajo or not password:
        return jsonify(
            {"success": False, "message": "Legajo y contraseña son requeridos"}
        )
    resultado = facial_controller.procesar_acceso_manual_totem(legajo, password)
    return jsonify(resultado)

@facial_bp.route("/verify_2fa", methods=["POST"])
def verify_2fa():
    """Verifica el token 2FA para el acceso manual."""
    facial_controller = FacialController()
    data = request.get_json()
    legajo = data.get("legajo")
    token = data.get("token")
    if not legajo or not token:
        return jsonify({"success": False, "message": "Legajo y token son requeridos"})
    
    resultado = facial_controller.verificar_token_2fa(legajo, token)
    if resultado.get("success"):
        # Añadir redirect_url en caso de éxito para el frontend
        resultado["redirect_url"] = url_for("facial.panel_totem")
        
    return jsonify(resultado)

@facial_bp.route("/resend_2fa", methods=["POST"])
def resend_2fa():
    """Reenvía el token 2FA para el acceso manual."""
    facial_controller = FacialController()
    data = request.get_json()
    legajo = data.get("legajo")
    if not legajo:
        return jsonify({"success": False, "message": "Legajo es requerido"})
    
    resultado = facial_controller.reenviar_token_2fa(legajo)
    return jsonify(resultado)


@facial_bp.route("/panel_totem")
def panel_totem():
    """Página de confirmación para entrada/salida del tótem."""
    return render_template("totem/panel_totem.html")


@facial_bp.route("/facial/register_face/<string:user_id>", methods=["POST"])
@permission_required('modificar_empleado')
def register_face(user_id):
    """Registro facial para un usuario existente (protegido por permiso)."""
    facial_controller = FacialController()
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"success": False, "error": "No se recibió imagen"})
    resultado = facial_controller.registrar_rostro(user_id, data["image"])
    return jsonify(resultado)
