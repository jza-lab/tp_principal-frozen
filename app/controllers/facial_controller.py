from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
import os
import cv2
import numpy as np
import base64
import re
from datetime import datetime, timedelta  # Agregar timedelta
import face_recognition
import json
import csv
import io
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import Database
from app.config import Config
from app.controllers.usuario_controller import UsuarioController
import logging
import secrets  # Agregar secrets

logger = logging.getLogger(__name__)

# Crear blueprint de autenticación
auth_bp = Blueprint('auth', __name__, template_folder='templates')

# Inicializar base de datos
db = Database().client

# Configuración de rutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "Data")
os.makedirs(SAVE_DIR, exist_ok=True)

# ====== FUNCIONES AUXILIARES ======

def registrar_acceso(usuario_id, tipo, metodo, dispositivo, observaciones=None):
    """Registra entrada/salida en la base de datos"""
    try:
        logger.info(f"📝 Registrando acceso: usuario={usuario_id}, tipo={tipo}, metodo={metodo}")

        registro_data = {
            "usuario_id": usuario_id,
            "fecha_hora": datetime.now().isoformat(),
            "tipo": tipo,
            "metodo": metodo,
            "dispositivo": dispositivo,
            "observaciones": observaciones
        }

        logger.info(f"📋 Datos del registro: {registro_data}")

        response = db.table("registros_acceso").insert(registro_data).execute()

        if response.data:
            logger.info(f"✅ Registro de {tipo} para usuario {usuario_id} - ID: {response.data[0].get('id')}")
            return True
        else:
            logger.error("❌ No se pudo insertar el registro")
            return False

    except Exception as e:
        logger.error(f"❌ Error registrando acceso: {e}")
        return False

def generar_token_acceso():
    """Genera un token único para acceso temporal"""
    return secrets.token_urlsafe(32)

# ====== RUTAS DE AUTENTICACIÓN ======

@auth_bp.route("/")
def index():
    """Página principal de login"""
    return render_template("login.html")

@auth_bp.route("/index")
def auth_index():
    """Alias para auth.index - redirige a la página principal"""
    return redirect(url_for("auth.index"))

@auth_bp.route("/login_face", methods=["POST"])
def login_face():
    """Login con reconocimiento facial"""
    data = request.get_json()
    image_data = re.sub('^data:image/.+;base64,', '', data['image'])
    image_bytes = base64.b64decode(image_data)

    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    face_encodings = face_recognition.face_encodings(frame)
    if not face_encodings:
        return jsonify({"success": False, "message": "❌ No se detectó rostro en la imagen"})

    input_encoding = face_encodings[0]

    try:
        # Obtener usuarios con facial_encoding de Supabase
        response = db.table("usuarios").select(
            "id, email, nombre, facial_encoding, rol, activo"
        ).not_.is_("facial_encoding", "null").eq("activo", True).execute()

        usuarios = response.data

        usuario_identificado = None
        usuario_nombre = None
        usuario_id = None

        for usuario in usuarios:
            if usuario.get('facial_encoding'):
                try:
                    known_encoding = np.array(json.loads(usuario['facial_encoding']))
                    match = face_recognition.compare_faces([known_encoding], input_encoding, tolerance=0.6)
                    if match[0]:
                        usuario_identificado = usuario['email']
                        usuario_nombre = usuario.get('nombre', '')
                        usuario_id = usuario.get('id')
                        break
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Error decodificando encoding para usuario {usuario['email']}: {e}")
                    continue

        if usuario_identificado:
            # REGISTRAR ENTRADA
            if not registrar_acceso(usuario_id, "ENTRADA", "FACIAL", "TOTEM"):
                return jsonify({"success": False, "message": "❌ Error registrando entrada"})

            # ACTIVAR ACCESO WEB usando el Controller
            usuario_controller = UsuarioController()
            resultado_activacion = usuario_controller.activar_login_totem(usuario_id)

            if not resultado_activacion.get('success'):
                logger.error(f"Error activando login tótem: {resultado_activacion.get('error')}")

            session["user_id"] = usuario_id
            session["user_email"] = usuario_identificado
            session["user_nombre"] = usuario_nombre
            session["es_totem"] = True

            return jsonify({
                "success": True,
                "message": "✅ Entrada registrada - Acceso web habilitado",
                "email": usuario_identificado,
                "nombre": usuario_nombre
            })

        return jsonify({"success": False, "message": "❌ Rostro no coincide con ningún usuario registrado"})

    except Exception as e:
        logger.error(f"Error en login facial: {str(e)}")
        return jsonify({"success": False, "message": f"❌ Error en el servidor: {str(e)}"})

@auth_bp.route("/logout_face", methods=["POST"])
def logout_face():
    """Logout desde tótem + desactivar acceso web"""
    try:
        user_id = session.get("user_id")
        logger.info(f"🚪 Iniciando logout para usuario ID: {user_id}")

        if user_id:
            # 1. Registrar salida
            logger.info("📝 Registrando salida en registros_acceso...")
            salida_registrada = registrar_acceso(user_id, "SALIDA", "FACIAL", "TOTEM")

            if salida_registrada:
                logger.info("✅ Salida registrada correctamente")
            else:
                logger.error("❌ Error registrando salida")

            # 2. DESACTIVAR ACCESO WEB usando el Controller
            logger.info("🔒 Desactivando flags de tótem...")
            usuario_controller = UsuarioController()
            resultado_desactivacion = usuario_controller.desactivar_login_totem(user_id)

            if resultado_desactivacion.get('success'):
                logger.info("✅ Flags de tótem desactivados correctamente")
            else:
                logger.error(f"❌ Error desactivando flags: {resultado_desactivacion.get('error')}")

            # 3. Verificación directa para confirmar
            logger.info("🔍 Verificando actualización en base de datos...")
            try:
                response = db.table("usuarios").select("login_totem_activo, ultimo_login_totem").eq("id", user_id).execute()
                if response.data:
                    usuario = response.data[0]
                    logger.info(f"📊 Estado después del logout:")
                    logger.info(f"   - login_totem_activo: {usuario.get('login_totem_activo')}")
                    logger.info(f"   - ultimo_login_totem: {usuario.get('ultimo_login_totem')}")
            except Exception as e:
                logger.error(f"Error en verificación: {e}")

        # 4. Limpiar sesión
        session.clear()
        logger.info("🧹 Sesión limpiada")

        return jsonify({"success": True, "message": "✅ Salida registrada correctamente"})

    except Exception as e:
        logger.error(f"❌ Error en logout: {e}")
        return jsonify({"success": False, "message": "Error al registrar salida"})
# ====== RUTAS WEB ======

@auth_bp.route("/login_totem")
def login_totem():
    """Página del tótem para reconocimiento facial"""
    return render_template("login_totem.html")

@auth_bp.route("/login_web_page")
def login_web_page():
    """Página de login web"""
    return render_template("login_web.html")

@auth_bp.route("/login_web", methods=["POST"])
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
        return redirect(url_for('auth.panel_web'))
    else:
        flash(resultado.get('error', 'Error de autenticación'), "error")
        return redirect(url_for('auth.login_web_page'))

@auth_bp.route("/panel_totem")
def panel_totem():
    """Panel después de login exitoso en tótem"""
    if not session.get('es_totem'):
        flash("Acceso no autorizado", "error")
        return redirect(url_for('auth.index'))

    # Pasar datetime al contexto de la plantilla
    from datetime import datetime
    return render_template("panel_totem.html", datetime=datetime)

@auth_bp.route("/debug_usuario/<legajo>")
def debug_usuario(legajo):
    """Ruta para diagnosticar el estado de un usuario"""
    try:
        usuario_controller = UsuarioController()

        # 1. Buscar usuario por legajo
        user_result = usuario_controller.model.find_by_legajo_v2(legajo)

        if not user_result.get('success') or not user_result.get('data'):
            return jsonify({"success": False, "error": "Usuario no encontrado"})

        user_data = user_result['data']

        # 2. Verificar estado de acceso
        verificacion = usuario_controller._verificar_login_totem_activo(user_data)

        # 3. Información detallada
        resultado = {
            "success": True,
            "usuario": {
                "id": user_data.get('id'),
                "legajo": user_data.get('legajo'),
                "email": user_data.get('email'),
                "activo": user_data.get('activo'),
                "login_totem_activo": user_data.get('login_totem_activo'),
                "ultimo_login_totem": user_data.get('ultimo_login_totem'),
                "ultimo_login_web": user_data.get('ultimo_login_web')
            },
            "verificacion_totem": verificacion,
            "fecha_actual": date.today().isoformat()
        }

        return jsonify(resultado)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@auth_bp.route("/panel_web")
def panel_web():
    """Panel web principal"""
    if 'user_id' not in session:
        flash("Debe iniciar sesión primero", "error")
        return redirect(url_for('auth.login_web_page'))

    # Verificar acceso usando el Controller
    usuario_controller = UsuarioController()
    verificacion = usuario_controller.verificar_acceso_web(session['user_id'])

    if not verificacion.get('success'):
        session.clear()
        flash(verificacion.get('error', 'Acceso no permitido'), "error")
        return redirect(url_for('auth.login_web_page'))

    return render_template("panel_web.html")

@auth_bp.route("/logout_web")
def logout_web():
    """Logout de la sesión web (no afecta el tótem)"""
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_nombre', None)
    session.pop('login_from_totem', None)
    flash("✅ Sesión web cerrada correctamente", "success")
    return redirect(url_for('auth.index'))

@auth_bp.route("/verificar_acceso")
def verificar_acceso():
    """Endpoint para verificar acceso desde JavaScript"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'No hay sesión activa'})

    usuario_controller = UsuarioController()
    verificacion = usuario_controller.verificar_acceso_web(session['user_id'])
    return jsonify(verificacion)

# ====== MIDDLEWARE ======

@auth_bp.before_request
def verificar_acceso_web():
    """Verifica que el usuario tenga login en tótem para acceder a la web"""
    # Excluir rutas públicas - INCLUIR panel_totem
    rutas_publicas = [
        'auth.index', 'auth.auth_index', 'auth.login_web', 'auth.login_face',
        'auth.logout_face', 'auth.login_totem', 'auth.login_web_page',
        'auth.registro_facial', 'auth.register_face_reject', 'auth.verificar_acceso',
        'auth.panel_totem',  # ← AGREGAR ESTA LÍNEA
        'static'
    ]

    if request.endpoint in rutas_publicas:
        return

    # Solo verificar acceso web para rutas que requieren sesión web
    if 'user_id' in session and not session.get('es_totem'):
        # Verificar que el login en tótem sigue activo usando el Controller
        try:
            usuario_controller = UsuarioController()
            verificacion = usuario_controller.verificar_acceso_web(session['user_id'])

            if not verificacion.get('success'):
                session.clear()
                flash("🚫 Acceso web expirado. Registre entrada en tótem", "error")
                return redirect(url_for("auth.index"))

        except Exception as e:
            logger.error(f"Error verificando acceso: {e}")
            session.clear()
            return redirect(url_for("auth.index"))

# ====== RUTAS EXISTENTES (mantener las que ya tenías) ======

@auth_bp.route("/register_face/<string:user_id>", methods=["GET", "POST"])
def registro_facial(user_id):
    """Registro facial para un usuario existente"""
    if request.method == "GET":
        # Obtener información del usuario para mostrar
        try:
            user_response = db.table("usuarios").select("nombre", "apellido", "email").eq("id", user_id).execute()
            if user_response.data:
                usuario = user_response.data[0]
                return render_template("capturar_rostro.html",
                                     user_id=user_id,
                                     usuario=usuario)
            else:
                flash("Usuario no encontrado", "error")
                return redirect(url_for("auth.register"))
        except Exception as e:
            logger.error(f"Error obteniendo usuario: {e}")
            flash("Error al cargar datos del usuario", "error")
            return redirect(url_for("auth.register"))

    if request.method == "POST":
        try:
            image_data = request.json.get("image")
            if not image_data:
                return jsonify({"success": False, "error": "No se recibió imagen"})

            # Procesar la imagen
            img_bytes = base64.b64decode(image_data.split(",")[1])
            img = face_recognition.load_image_file(io.BytesIO(img_bytes))
            encodings = face_recognition.face_encodings(img)

            if not encodings:
                return jsonify({"success": False, "error": "No se detectó ningún rostro"})

            encoding = encodings[0].tolist()

            # Actualizar usuario con encoding facial
            response = db.table("usuarios").update({
                "facial_encoding": json.dumps(encoding),
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()

            if response.data:
                # Limpiar sesión de registro pendiente
                session.pop('pending_facial_user_id', None)
                return jsonify({"success": True, "message": "✅ Registro facial completado correctamente."})
            else:
                return jsonify({"success": False, "error": "Error al actualizar el usuario"})

        except Exception as e:
            logger.error(f"Error en registro facial: {e}")
            return jsonify({"success": False, "error": str(e)})

@auth_bp.route("/register_face_reject", methods=["POST"])
def register_face_reject():
    """Rechazar registro facial y eliminar usuario"""
    email = session.get("user_email")
    user_id = session.get("user_id")

    if email and user_id:
        try:
            # Eliminar usuario de Supabase
            db.table("usuarios").delete().eq("id", user_id).execute()
        except Exception as e:
            logger.error(f"Error eliminando usuario: {e}")

        # Limpiar sesión
        session.pop("user_email", None)
        session.pop("user_id", None)
        session.pop("user_nombre", None)

    return render_template("register.html", rejected=True)
