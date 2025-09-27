from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
import os
import cv2
import numpy as np
import base64
import re
from datetime import datetime
import face_recognition
import json
import csv
import io
from werkzeug.security import generate_password_hash, check_password_hash
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
