from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash,
)
from app.controllers.facial_controller import FacialController
from app.controllers.usuario_controller import UsuarioController
from app.utils.decorators import roles_required
import logging

logger = logging.getLogger(__name__)

# Crear blueprint de autenticación facial
facial_bp = Blueprint("facial", __name__, template_folder="templates")

@facial_bp.route("/")
def index():
    session.clear()
    """Página principal - redirigir al tótem"""
    return render_template("totem/login_totem.html")


@facial_bp.route("/index")
def facial_index():
    """Alias para facial.index"""
    session.clear()
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
        if tipo_acceso == "SALIDA":
            session.clear()
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
    if resultado.get("success"):
        return jsonify(
            {
                "success": True,
                "message": resultado.get("message"),
                "tipo_acceso": resultado.get("tipo_acceso"),
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


@facial_bp.route("/panel_totem")
def panel_totem():
    """Página de confirmación para entrada/salida del tótem."""
    return render_template("totem/panel_totem.html")


@facial_bp.route("/facial/register_face/<string:user_id>", methods=["POST"])
@roles_required(allowed_roles=["GERENTE", "RRHH", "IT"])
def register_face(user_id):
    """Registro facial para un usuario existente (protegido por rol)."""
    facial_controller = FacialController()
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"success": False, "error": "No se recibió imagen"})
    resultado = facial_controller.registrar_rostro(user_id, data["image"])
    return jsonify(resultado)
