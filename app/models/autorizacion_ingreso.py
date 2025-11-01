from .base_model import BaseModel
from datetime import date, datetime
from collections import defaultdict
import logging
import pytz

logger = logging.getLogger(__name__)

class AutorizacionIngresoModel(BaseModel):
    """
    Modelo para interactuar con la tabla de autorizaciones de ingreso (`u_autorizaciones_ingreso`).
    """
    def get_table_name(self) -> str:
        """Retorna el nombre de la tabla de la base de datos."""
        return 'u_autorizaciones_ingreso'

    def create(self, data: dict) -> dict:
        """
        Crea un nuevo registro de autorización de ingreso, asegurando el estado 'PENDIENTE'.
        """
        try:
            data['estado'] = 'PENDIENTE'
            
            # La lógica de "upsert" se maneja mejor en el controlador si es necesario.
            # El modelo debe tener una responsabilidad clara: crear un registro.
            response = self.db.table(self.get_table_name()).insert(data).execute()

            if response.data:
                return {'success': True, 'data': response.data[0]}
            
            return {'success': False, 'error': 'No se pudo crear la autorización.'}
        except Exception as e:
            logger.error(f"Error al crear autorización: {e}", exc_info=True)
            # Manejo de error específico para duplicados si hay una constraint a nivel de BD.
            if "duplicate key value" in str(e):
                return {'success': False, 'error': 'Ya existe una autorización de este tipo para el usuario en la fecha especificada.'}
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def find_by_usuario_and_fecha(self, usuario_id: int, fecha: date, tipo: str = None, estado: str = None) -> dict:
        """
        Busca autorizaciones para un usuario y fecha específicos.
        Devuelve siempre una lista de resultados para manejar múltiples autorizaciones.
        """
        try:
            select_query = "*, turno:fk_turno_autorizado(nombre, hora_inicio, hora_fin)"
            
            query = self.db.table(self.get_table_name())\
                .select(select_query)\
                .eq("usuario_id", usuario_id)\
                .eq("fecha_autorizada", fecha.isoformat())

            if tipo:
                query = query.eq('tipo', tipo)
            if estado:
                query = query.eq('estado', estado)

            response = query.execute()
            
            return {'success': True, 'data': response.data or []}
            
        except Exception as e:
            logger.error(f"Error al buscar autorización para usuario {usuario_id} en {fecha}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def find_all_grouped_by_status(self) -> dict:
        """
        Obtiene todas las autorizaciones y las devuelve agrupadas por su estado.
        Esto optimiza la carga de datos para la UI, que necesita tanto las pendientes como el historial en una sola operación.
        """
        try:
            select_query = "*, usuario:usuario_id(nombre, apellido, legajo), turno:turno_autorizado_id(nombre, hora_inicio, hora_fin)"

            response = self.db.table(self.get_table_name()).select(select_query)\
                .order('fecha_autorizada', desc=True).execute()

            grouped_data = defaultdict(list)
            if response.data:
                art_tz = pytz.timezone('America/Argentina/Buenos_Aires')
                for item in response.data:
                    fecha_str = item.get('fecha_autorizada')
                    if fecha_str:
                        try:
                            # Supabase devuelve un timestamp en formato ISO 8601 (ej. '2023-10-31T00:00:00+00:00')
                            # Lo parseamos a un objeto datetime con conciencia de zona horaria (UTC)
                            utc_dt = datetime.fromisoformat(fecha_str)
                            
                            # Lo convertimos a la zona horaria de Argentina
                            art_dt = utc_dt.astimezone(art_tz)
                            
                            # Formateamos la fecha de vuelta a un string 'YYYY-MM-DD'
                            # Esto evita que JavaScript la reinterprete incorrectamente
                            item['fecha_autorizada'] = art_dt.strftime('%Y-%m-%d')
                        except (ValueError, TypeError):
                            logger.warning(f"No se pudo parsear la fecha '{fecha_str}'. Se dejará el valor original.")

                    grouped_data[item['estado']].append(item)
            
            return {'success': True, 'data': grouped_data}
        except Exception as e:
            logger.error(f"Error al buscar y agrupar autorizaciones: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}

    def update_estado(self, autorizacion_id: int, estado: str, comentario: str = None) -> dict:
        """
        Actualiza el estado y el comentario de una autorización específica.
        """
        try:
            update_data = {"estado": estado}
            if comentario is not None:
                update_data["comentario_supervisor"] = comentario

            response = self.db.table(self.get_table_name())\
                .update(update_data)\
                .eq("id", autorizacion_id)\
                .execute()
            
            if response.data:
                return {'success': True, 'data': response.data[0]}
            
            return {'success': False, 'error': 'No se pudo actualizar la autorización o no fue encontrada.'}
        except Exception as e:
            logger.error(f"Error al actualizar estado de autorización {autorizacion_id}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error en la base de datos: {e}"}
