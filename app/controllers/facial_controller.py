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
import logging

logger = logging.getLogger(__name__)

class FacialController:
    """
    Controlador de lógica de negocio para todas las operaciones faciales y de registro de asistencia.
    """
    def __init__(self):
        self.db = Database().client
        # Asegurarse de que el directorio de datos exista
        self.save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data")
        os.makedirs(self.save_dir, exist_ok=True)

    def _get_image_from_data_url(self, image_data_url):
        """Decodifica una imagen en formato data URL a un frame de OpenCV."""
        try:
            image_data = re.sub('^data:image/.+;base64,', '', image_data_url)
            image_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            logger.error(f"Error decodificando imagen: {e}")
            return None

    def identificar_rostro(self, image_data_url):
        """
        Intenta identificar un usuario a partir de una imagen facial.
        Devuelve los datos del usuario si se encuentra una coincidencia.
        """
        frame = self._get_image_from_data_url(image_data_url)
        if frame is None:
            return {'success': False, 'message': 'Error al procesar la imagen.'}

        face_encodings = face_recognition.face_encodings(frame)
        if not face_encodings:
            return {'success': False, 'message': 'No se detectó rostro en la imagen'}

        input_encoding = face_encodings[0]

        try:
            response = self.db.table("usuarios").select("id, email, nombre, facial_encoding").not_.is_("facial_encoding", "null").eq("activo", True).execute()
            usuarios = response.data

            for usuario in usuarios:
                if usuario.get('facial_encoding'):
                    try:
                        known_encoding = np.array(json.loads(usuario['facial_encoding']))
                        if face_recognition.compare_faces([known_encoding], input_encoding, tolerance=0.6)[0]:
                            return {'success': True, 'usuario': usuario}
                    except (json.JSONDecodeError, TypeError):
                        continue

            return {'success': False, 'message': 'Rostro no reconocido.'}
        except Exception as e:
            logger.error(f"Error en la base de datos durante la identificación facial: {e}")
            return {'success': False, 'message': 'Error del servidor.'}

    def registrar_rostro(self, user_id, image_data_url):
        """Registra un rostro para un usuario específico."""
        frame = self._get_image_from_data_url(image_data_url)
        if frame is None:
            return {'success': False, 'message': 'Error al procesar la imagen.'}

        new_encodings = face_recognition.face_encodings(frame)
        if not new_encodings:
            return {'success': False, 'message': 'No se detectó rostro en la imagen.'}

        new_encoding_json = json.dumps(new_encodings[0].tolist())

        try:
            self.db.table("usuarios").update({"facial_encoding": new_encoding_json}).eq("id", user_id).execute()
            return {'success': True}
        except Exception as e:
            logger.error(f"Error en la base de datos durante el registro facial: {e}")
            return {'success': False, 'message': 'Error del servidor al guardar el rostro.'}

    def registrar_ingreso_csv(self, user_data):
        """Registra el ingreso de un usuario en un archivo CSV."""
        try:
            csv_path = os.path.join(self.save_dir, "ingresos_egresos.csv")
            fieldnames = ['id_registro', 'id_empleado', 'nombre', 'apellido', 'fecha', 'hora_ingreso', 'hora_egreso', 'area']

            registros = []
            if os.path.exists(csv_path):
                with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    if set(reader.fieldnames) == set(fieldnames):
                        registros = list(reader)

            ahora = datetime.now()
            fecha_actual = ahora.strftime("%d/%m/%Y")

            if not any(str(r.get('id_empleado')) == str(user_data.get('id')) and r.get('fecha') == fecha_actual and not r.get('hora_egreso') for r in registros):
                nuevo_id = len(registros) + 1
                registros.append({
                    'id_registro': str(nuevo_id),
                    'id_empleado': str(user_data.get('id')),
                    'nombre': user_data.get('nombre', ''),
                    'apellido': user_data.get('apellido', ''),
                    'fecha': fecha_actual,
                    'hora_ingreso': ahora.strftime("%H:%M"),
                    'hora_egreso': '',
                    'area': user_data.get('departamento', 'Sistema')
                })
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(registros)
        except Exception as e:
            logger.error(f"Error registrando ingreso en CSV: {e}")

    def registrar_egreso_csv(self, user_data):
        """Registra el egreso de un usuario en un archivo CSV."""
        try:
            csv_path = os.path.join(self.save_dir, "ingresos_egresos.csv")
            if not os.path.exists(csv_path):
                return

            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                registros = list(reader)

            ahora = datetime.now()
            fecha_actual = ahora.strftime("%d/%m/%Y")

            for registro in reversed(registros):
                if str(registro.get('id_empleado')) == str(user_data.get('id')) and registro.get('fecha') == fecha_actual and not registro.get('hora_egreso'):
                    registro['hora_egreso'] = ahora.strftime("%H:%M")
                    break

            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=registros[0].keys())
                writer.writeheader()
                writer.writerows(registros)
        except Exception as e:
            logger.error(f"Error registrando egreso en CSV: {e}")