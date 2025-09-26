from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
import os
import cv2
import numpy as np
import base64
import re
from datetime import datetime
import face_recognition
import json
import csv
from app.database import Database
from app.config import Config
import logging

logger = logging.getLogger(__name__)

# Crear blueprint de autenticación
auth_bp = Blueprint('auth', __name__, template_folder='templates')

# Inicializar base de datos
db = Database().client

# Configuración de rutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "Data")
os.makedirs(SAVE_DIR, exist_ok=True)

# ====== RUTAS DE AUTENTICACIÓN ======

@auth_bp.route("/")
def index():
    """Página principal de login"""
    return render_template("login.html")

@auth_bp.route("/login", methods=["POST"])
def login():
    """Login con email y contraseña"""
    email = request.form["email"]
    password = request.form["password"]

    # Verificar coincidencia con rostro detectado
    pending_user = session.get("pending_face_user")
    if pending_user and email != pending_user:
        error = "❌ El email no coincide con el rostro detectado"
        return render_template("login.html", error=error)

    try:
        # Buscar usuario en Supabase
        response = db.table("usuarios").select("*").eq("email", email).execute()

        if not response.data:
            error = "❌ Usuario no encontrado"
            return render_template("login.html", error=error)

        user = response.data[0]

        # Verificar contraseña (en producción usar hashing)
        if user.get('password_hash') != password:
            error = "❌ Contraseña incorrecta"
            return render_template("login.html", error=error)

        # Verificar si el usuario está activo
        if not user.get('active', True):
            error = "❌ Usuario inactivo"
            return render_template("login.html", error=error)

        # Establecer sesión
        session["user"] = user["email"]
        session["user_id"] = user["id"]
        session["role"] = user.get("rol", "operador")
        session["nombre"] = user.get("nombre", "")
        session["user_data"] = user  # Guardar datos completos del usuario

        # Completar autenticación facial si estaba pendiente
        if session.get("pending_face_user"):
            session["authenticated"] = True
            session.pop("pending_face_user", None)

        # Registrar ingreso automático
        registrar_ingreso_automatico(user)

        return redirect(url_for("auth.dashboard"))

    except Exception as e:
        logger.error(f"Error en login: {str(e)}")
        error = f"❌ Error en el login: {str(e)}"
        return render_template("login.html", error=error)

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
            "id, email, nombre, facial_encoding, rol, active"
        ).not_.is_("facial_encoding", "null").eq("active", True).execute()

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
            session["pending_face_user"] = usuario_identificado
            session["pending_face_user_id"] = usuario_id
            return jsonify({
                "success": True,
                "message": "✅ Rostro identificado. Por favor, ingrese su email y contraseña.",
                "email": usuario_identificado,
                "nombre": usuario_nombre
            })

        return jsonify({"success": False, "message": "❌ Rostro no coincide con ningún usuario registrado"})

    except Exception as e:
        logger.error(f"Error en login facial: {str(e)}")
        return jsonify({"success": False, "message": f"❌ Error en el servidor: {str(e)}"})

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Registro de nuevo usuario"""
    error = None
    success = None
    require_face = False

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        nombre = request.form["nombre"]
        apellido = request.form.get("apellido", "")
        role = request.form.get("role", "operador")

        if password != confirm_password:
            error = "❌ Las contraseñas no coinciden"
            return render_template("register.html", error=error)

        try:
            # Verificar si el usuario ya existe
            existing_user = db.table("usuarios").select("email").eq("email", email).execute()
            if existing_user.data:
                error = "❌ El usuario ya existe"
                return render_template("register.html", error=error)

            # Crear nuevo usuario en Supabase
            nuevo_usuario = {
                "email": email,
                "password_hash": password,  # ⚠️ En producción usar bcrypt
                "nombre": nombre,
                "apellido": apellido,
                "rol": role,
                "active": True,
                "created_at": datetime.now().isoformat(),
                "numero_empleado": request.form.get("numero_empleado", ""),
                "dni": request.form.get("dni", ""),
                "telefono": request.form.get("telefono", ""),
                "departamento": request.form.get("departamento", ""),
                "puesto": request.form.get("puesto", "")
            }

            response = db.table("usuarios").insert(nuevo_usuario).execute()

            if response.data:
                # Guardar datos en sesión para registro facial
                session["user_email"] = email
                session["user_nombre"] = nombre
                session["user_id"] = response.data[0]["id"]
                require_face = True
                success = "Usuario registrado correctamente. Por favor, registra tu rostro para finalizar."
            else:
                error = "❌ Error al registrar el usuario"

        except Exception as e:
            logger.error(f"Error en registro: {str(e)}")
            error = f"❌ Error al registrar el usuario: {str(e)}"

    return render_template("register.html", error=error, success=success, require_face=require_face)

@auth_bp.route("/register_face", methods=["POST"])
def register_face():
    """Registro de rostro para usuario"""
    data = request.get_json()
    image_data = re.sub('^data:image/.+;base64,', '', data['image'])
    image_bytes = base64.b64decode(image_data)

    email = session.get("user_email")
    user_id = session.get("user_id")

    if not email or not user_id:
        return jsonify({"error": "No se pudo registrar el rostro del usuario"}), 400

    # Convertir a imagen OpenCV
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Obtener encoding del rostro
    new_encodings = face_recognition.face_encodings(frame)
    if not new_encodings:
        return jsonify({"error": "No se detectó rostro en la imagen"}), 400

    new_encoding = new_encodings[0]

    try:
        # Actualizar usuario con facial_encoding en Supabase
        response = db.table("usuarios").update({
            "facial_encoding": json.dumps(new_encoding.tolist()),
            "updated_at": datetime.now().isoformat()
        }).eq("id", user_id).execute()

        if response.data:
            # Limpiar sesión de registro
            session.pop("user_email", None)
            session.pop("user_id", None)
            session.pop("user_nombre", None)

            return jsonify({
                "success": "✅ Registro completado correctamente.",
                "redirect": url_for("auth.index")
            })
        else:
            return jsonify({"error": "Error al actualizar el registro facial"}), 400

    except Exception as e:
        logger.error(f"Error en registro facial: {str(e)}")
        return jsonify({"error": f"Error en el servidor: {str(e)}"}), 500

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

@auth_bp.route("/dashboard")
def dashboard():
    """Dashboard principal"""
    email = session.get("user", "Usuario")
    nombre = session.get("nombre", "")
    role = session.get("role", "operador")

    if role.upper() == "ADMIN":
        return render_template("dashboard_admin.html", username=nombre, email=email)
    else:
        return render_template("dashboard_operador.html", username=nombre, email=email)

@auth_bp.route("/logout")
def logout():
    """Cerrar sesión"""
    if "user" in session:
        email = session["user"]
        nombre = session.get("nombre", "")

        # Registrar egreso automático
        registrar_egreso_automatico(email, nombre)

        if session.get("egreso_registrado"):
            mensaje = "✅ Egreso registrado correctamente. Sesión cerrada."
        else:
            mensaje = "ℹ️ Sesión cerrada (sin registro de egreso)"
    else:
        mensaje = "ℹ️ Sesión cerrada"

    # Limpiar sesión completa
    session.clear()

    return redirect(url_for("auth.index", mensaje=mensaje))

# ====== FUNCIONES AUXILIARES ======

def registrar_ingreso_automatico(user_data):
    """Registrar ingreso automático en CSV"""
    try:
        ahora = datetime.now()
        fecha_actual = ahora.strftime("%d/%m/%Y")
        hora_actual = ahora.strftime("%H:%M")

        csv_path = os.path.join(SAVE_DIR, "ingresos_egresos.csv")
        fieldnames = ['id_registro', 'id_empleado', 'nombre', 'apellido',
                     'fecha', 'hora_ingreso', 'hora_egreso', 'area']

        # Leer archivo existente o crear nuevo
        registros = []
        file_exists = os.path.exists(csv_path)

        if file_exists:
            try:
                with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    if reader.fieldnames == fieldnames:
                        registros = list(reader)
            except Exception as e:
                logger.error(f"Error leyendo CSV: {e}")

        # Verificar si ya tiene ingreso sin egreso hoy
        tiene_ingreso_sin_egreso = any(
            registro.get('id_empleado') == str(user_data.get('id')) and
            registro.get('fecha') == fecha_actual and
            registro.get('hora_ingreso') and
            not registro.get('hora_egreso')
            for registro in registros
        )

        if not tiene_ingreso_sin_egreso:
            nuevo_id = len(registros) + 1
            nuevo_registro = {
                'id_registro': str(nuevo_id),
                'id_empleado': str(user_data.get('id')),
                'nombre': user_data.get('nombre', ''),
                'apellido': user_data.get('apellido', ''),
                'fecha': fecha_actual,
                'hora_ingreso': hora_actual,
                'hora_egreso': '',
                'area': user_data.get('departamento', 'Sistema')
            }

            registros.append(nuevo_registro)

            # Escribir archivo CSV
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(registros)

            logger.info(f"Ingreso registrado para {user_data.get('nombre')}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error registrando ingreso: {e}")
        return False

def registrar_egreso_automatico(email, nombre):
    """Registrar egreso automático en CSV"""
    try:
        ahora = datetime.now()
        fecha_actual = ahora.strftime("%d/%m/%Y")
        hora_actual = ahora.strftime("%H:%M")

        csv_path = os.path.join(SAVE_DIR, "ingresos_egresos.csv")
        fieldnames = ['id_registro', 'id_empleado', 'nombre', 'apellido',
                     'fecha', 'hora_ingreso', 'hora_egreso', 'area']

        if not os.path.exists(csv_path):
            return False

        # Leer registros existentes
        with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            if reader.fieldnames != fieldnames:
                return False
            registros = list(reader)

        # Buscar y actualizar registro
        registro_actualizado = False
        for registro in registros:
            if (registro.get('nombre') == nombre and
                registro.get('fecha') == fecha_actual and
                registro.get('hora_ingreso') and
                not registro.get('hora_egreso')):

                registro['hora_egreso'] = hora_actual
                registro_actualizado = True
                break

        if registro_actualizado:
            # Escribir registros actualizados
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(registros)

            session["egreso_registrado"] = True
            logger.info(f"Egreso registrado para {nombre}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error registrando egreso: {e}")
        return False