from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from app.controllers.facial_controller import FacialController
from app.controllers.usuario_controller import UsuarioController
import logging

logger = logging.getLogger(__name__)

# Crear blueprint de autenticación facial
facial_bp = Blueprint('facial', __name__)

# ====== RUTAS PRINCIPALES ======

@facial_bp.route("/")
def index():
    """Página principal - redirigir al tótem"""
    return redirect(url_for('facial.login_totem'))

@facial_bp.route("/index")
def facial_index():
    """Alias para facial.index"""
    return redirect(url_for('facial.login_totem'))

# ====== RUTAS FACIALES ======

@facial_bp.route("/facial/login_face", methods=["POST"])
def login_face():
    """Login con reconocimiento facial"""
    facial_controller = FacialController()

    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"success": False, "message": "❌ No se recibió imagen"})

    resultado = facial_controller.procesar_login_facial(data['image'])

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

@facial_bp.route("/facial/logout_face", methods=["POST"])
def logout_face():
    """Logout desde tótem + desactivar acceso web"""
    facial_controller = FacialController()

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "❌ No hay sesión activa"})

    resultado = facial_controller.procesar_logout_facial(user_id)

    # Limpiar sesión siempre
    session.clear()

    return jsonify(resultado)

@facial_bp.route("/facial/login_totem")
def login_totem():
    """Página del tótem para reconocimiento facial"""
    return render_template("usuarios/login_totem.html")

@facial_bp.route("/facial/panel_totem")
def panel_totem():
    """Panel después de login exitoso en tótem"""
    if not session.get('es_totem'):
        flash("Acceso no autorizado", "error")
        return redirect(url_for("facial.login_totem"))

    from datetime import datetime
    return render_template("usuarios/panel_totem.html", now=datetime.now())

# ====== RUTAS WEB (para acceso desde navegador) ======

@facial_bp.route("/facial/login_web_page")
def login_web_page():
    """Página de login web"""
    return render_template("usuarios/login.html")

@facial_bp.route("/facial/login_web", methods=["POST"])
def login_web():
    """Procesar login web"""
    legajo = request.form.get('legajo')
    password = request.form.get('password')

    usuario_controller = UsuarioController()
    resultado = usuario_controller.autenticar_usuario_V2(legajo, password)

    if resultado.get('success'):
        user_data = resultado['data']
        session['user_id'] = user_data['id']
        session['user_email'] = user_data['email']
        session['user_nombre'] = user_data.get('nombre', 'Usuario')
        session['login_from_totem'] = True

        flash(f"✅ Bienvenido/a {user_data.get('nombre', 'Usuario')}", "success")
        return redirect(url_for('facial.panel_web'))
    else:
        flash(resultado.get('error', 'Error de autenticación'), "error")
        return redirect(url_for('facial.login_web_page'))

@facial_bp.route("/facial/verificar_acceso")
def verificar_acceso():
    """Endpoint para verificar acceso desde JavaScript"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'No hay sesión activa'})

    usuario_controller = UsuarioController()
    verificacion = usuario_controller.verificar_acceso_web(session['user_id'])
    return jsonify(verificacion)

@facial_bp.route("/facial/panel_web")
def panel_web():
    """Panel web principal"""
    if 'user_id' not in session:
        flash("Debe iniciar sesión primero", "error")
        return redirect(url_for('facial.login_web_page'))

    # Verificar acceso usando el Controller
    usuario_controller = UsuarioController()
    verificacion = usuario_controller.verificar_acceso_web(session['user_id'])

    if not verificacion.get('success'):
        session.clear()
        flash(verificacion.get('error', 'Acceso no permitido'), "error")
        return redirect(url_for('facial.login_web_page'))

    return render_template("usuarios/panel_web.html")

@facial_bp.route("/facial/logout_web")
def logout_web():
    """Logout de la sesión web (no afecta el tótem)"""
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_nombre', None)
    session.pop('login_from_totem', None)
    flash("✅ Sesión web cerrada correctamente", "success")
    return redirect(url_for('facial.login_totem'))

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