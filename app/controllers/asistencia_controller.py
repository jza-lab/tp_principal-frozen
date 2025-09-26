from controllers.base_controller import BaseController
from models.asistencia import AsistenciaModel
from schemas.asistencia_schema import AsistenciaSchema
from typing import Dict
from marshmallow import ValidationError
from datetime import date

class AsistenciaController(BaseController):
    """
    Controlador para la lógica de negocio de los registros de asistencia.
    """
    def __init__(self):
        super().__init__()
        self.model = AsistenciaModel()
        self.schema = AsistenciaSchema()

    def registrar_entrada(self, usuario_id: int) -> Dict:
        """
        Registra un fichaje de entrada para un usuario.
        Verifica que no haya una entrada ya registrada para el día.
        """
        try:
            # Verificar si ya existe una entrada para hoy
            today_str = date.today().isoformat()
            existing_entry = self.model.db.table(self.model.get_table_name()) \
                .select('id') \
                .eq('usuario_id', usuario_id) \
                .eq('tipo', 'ENTRADA') \
                .gte('fecha_hora', f"{today_str}T00:00:00") \
                .lte('fecha_hora', f"{today_str}T23:59:59") \
                .execute()

            if existing_entry.data:
                return {'success': False, 'error': 'Ya se ha registrado una entrada para hoy.'}

            # Crear el registro de entrada
            datos_asistencia = {'usuario_id': usuario_id, 'tipo': 'ENTRADA'}
            validated_data = self.schema.load(datos_asistencia)
            return self.model.create(validated_data)

        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}

    def registrar_salida(self, usuario_id: int) -> Dict:
        """
        Registra un fichaje de salida para un usuario.
        Verifica que exista una entrada previa y que no haya ya una salida.
        """
        try:
            today_str = date.today().isoformat()
            # Verificar que exista una entrada hoy
            entry = self.model.db.table(self.model.get_table_name()) \
                .select('id') \
                .eq('usuario_id', usuario_id) \
                .eq('tipo', 'ENTRADA') \
                .gte('fecha_hora', f"{today_str}T00:00:00") \
                .lte('fecha_hora', f"{today_str}T23:59:59") \
                .execute()

            if not entry.data:
                return {'success': False, 'error': 'No se puede registrar una salida sin una entrada previa hoy.'}

            # Verificar que no exista ya una salida hoy
            exit_entry = self.model.db.table(self.model.get_table_name()) \
                .select('id') \
                .eq('usuario_id', usuario_id) \
                .eq('tipo', 'SALIDA') \
                .gte('fecha_hora', f"{today_str}T00:00:00") \
                .lte('fecha_hora', f"{today_str}T23:59:59") \
                .execute()

            if exit_entry.data:
                return {'success': False, 'error': 'Ya se ha registrado una salida para hoy.'}

            # Crear el registro de salida
            datos_asistencia = {'usuario_id': usuario_id, 'tipo': 'SALIDA'}
            validated_data = self.schema.load(datos_asistencia)
            return self.model.create(validated_data)

        except ValidationError as e:
            return {'success': False, 'error': f"Datos inválidos: {e.messages}"}
        except Exception as e:
            return {'success': False, 'error': f'Error interno: {str(e)}'}