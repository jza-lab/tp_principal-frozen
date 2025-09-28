from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from app.controllers.facial_controller import FacialController
from app.controllers.usuario_controller import UsuarioController
import logging

logger = logging.getLogger(__name__)

# Crear blueprint de autenticación facial
facial_bp = Blueprint('facial', __name__, template_folder='templates')

# ====== RUTAS PRINCIPALES ======

@facial_bp.route("/")
def index():
    session.clear()
    """Página principal - redirigir al tótem"""
    return render_template("totem/login_totem.html")

@facial_bp.route("/index")
def facial_index():
    """Alias para facial.index"""
    session.clear()
    return redirect(url_for('facial.login_totem'))

# ====== RUTAS FACIALES ======
@facial_bp.route("/login_face", methods=["POST", "GET", "PUT"])
def login_face():
    """Login con reconocimiento facial"""
    facial_controller = FacialController()

    if(request.method == 'POST' or request.method == 'PUT'):
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({"success": False, "message": "❌ No se recibió imagen"})

        resultado = facial_controller.procesar_login_facial_totem(data['image'])

        if resultado.get('success'):
            usuario = resultado['usuario']

            # Configurar sesión
            session["user_id"] = usuario['id']
            session["user_email"] = usuario['email']
            session["user_nombre"] = usuario['nombre']
            session["es_totem"] = True

            return jsonify({
                "success": True,
                "message": resultado['message'],
                "email": usuario['email'],
                "nombre": usuario['nombre'],
                "redirect_url": url_for("facial.panel_totem")
            })
        else:
            return jsonify({
                "success": False,
                "message": resultado.get('message', 'Error desconocido')
            })
    
    return render_template("totem/login_totem.html")

@facial_bp.route("/logout_face", methods=["POST"])
def logout_face():
    """Logout desde tótem + desactivar acceso web"""
    facial_controller = FacialController()

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "❌ No hay sesión activa"})

    resultado = facial_controller.procesar_logout_facial_totem(user_id)

    # Limpiar sesión siempre
    session.clear()

    return jsonify(resultado)

@facial_bp.route("/panel_totem")
def panel_totem():
    """Panel después de login exitoso en tótem"""
    if not session.get('es_totem'):
        flash("Acceso no autorizado", "error")
        return redirect(url_for("facial.login_face"))
    
    from datetime import datetime
    return render_template("totem/panel_totem.html", now=datetime.now())

# ====== RUTAS ADICIONALES ======

@facial_bp.route("/facial/register_face/<string:user_id>", methods=["POST"])
def register_face(user_id):
    """Registro facial para un usuario existente"""
    facial_controller = FacialController()

    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"success": False, "error": "No se recibió imagen"})

    resultado = facial_controller.registrar_rostro(user_id, data['image'])

    if resultado.get('success'):
        session.pop('pending_facial_user_id', None)

    return jsonify(resultado)

@facial_bp.route("/facial/debug_registros/<int:usuario_id>")
def debug_registros(usuario_id):
    """Ver todos los registros de acceso de un usuario"""
    try:
        from app.database import Database
        db = Database().client

        response = db.table("registros_acceso").select("*").eq("usuario_id", usuario_id).order("fecha_hora", desc=True).execute()
        usuario_response = db.table("usuarios").select("id, email, nombre, login_totem_activo, ultimo_login_totem").eq("id", usuario_id).execute()

        resultado = {
            "success": True,
            "usuario": usuario_response.data[0] if usuario_response.data else None,
            "total_registros": len(response.data),
            "registros": response.data
        }

        return jsonify(resultado)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@facial_bp.route("/facial/debug_estado")
def debug_estado():
    """Diagnóstico del estado actual del sistema facial"""
    try:
        from app.database import Database
        db = Database().client

        response = db.table("usuarios").select("id").not_.is_("facial_encoding", "null").eq("activo", True).execute()
        registros_response = db.table("registros_acceso").select("*").order("fecha_hora", desc=True).limit(5).execute()

        return jsonify({
            "success": True,
            "usuarios_con_facial_encoding": len(response.data),
            "ultimos_registros": registros_response.data,
            "sesion_actual": {
                "user_id": session.get("user_id"),
                "user_email": session.get("user_email"),
                "es_totem": session.get("es_totem")
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})