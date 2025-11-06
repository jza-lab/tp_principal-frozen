import logging
from app.models.base_model import BaseModel
from app.schemas.issue_planificacion_schema import IssuePlanificacionSchema
from typing import Dict
from datetime import datetime # Importar datetime

logger = logging.getLogger(__name__)

class IssuePlanificacionModel(BaseModel):
    """
    Modelo para gestionar la tabla 'issues_planificacion'.
    """


    def get_table_name(self) -> str:
        return "issues_planificacion"

    def get_all_with_op_details(self) -> Dict:
        """
        Obtiene todos los issues PENDIENTES, uniendo los datos clave
        de la orden de producción asociada (OP) y el nombre del producto.
        """
        try:
            # --- ¡CONSULTA CORREGIDA! ---
            # Ahora hacemos un join anidado: issues -> ordenes_produccion -> productos
            query = self.db.table(self.get_table_name()) \
                          .select("*, orden_produccion:ordenes_produccion!inner(id, codigo, cantidad_planificada, fecha_meta, linea_asignada, productos(nombre))") \
                          .eq("estado", "PENDIENTE") \
                          .order("created_at", desc=True)

            response = query.execute()

            # --- LÓGICA DE APLANAMIENTO CORREGIDA ---
            data = []
            for item in response.data:
                op_data = item.pop('orden_produccion', {})
                if op_data: # Asegurarse de que op_data no esté vacío
                    item['op_codigo'] = op_data.get('codigo')

                    # Extraer el nombre del producto anidado
                    producto_data = op_data.pop('productos', {})
                    item['op_producto_nombre'] = producto_data.get('nombre', 'N/A')

                    item['op_cantidad'] = op_data.get('cantidad_planificada')
                    item['op_fecha_meta'] = op_data.get('fecha_meta')
                    item['op_linea_sugerida'] = op_data.get('linea_asignada')

                data.append(item)

            return {'success': True, 'data': data}

        except Exception as e:
            logger.error(f"Error en get_all_with_op_details (IssuePlanificacionModel): {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def find_by_op_id(self, op_id: int) -> Dict:
        """ Busca un issue por el ID de la orden de producción. """
        return self.find_all(filters={'orden_produccion_id': op_id}, limit=1)

    def delete_by_op_id(self, op_id: int) -> Dict:
        """ Elimina un issue usando el ID de la orden de producción. """
        try:
            self.db.table(self.get_table_name()).delete().eq('orden_produccion_id', op_id).execute()
            return {'success': True}
        except Exception as e:
            logger.error(f"Error al eliminar issue por op_id {op_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def create_or_update_by_op_id(self, op_id: int, issue_data: Dict) -> Dict:
        """
        Intenta crear un issue. Si ya existe uno (violación de 'UNIQUE'),
        actualiza el existente.
        """
        try:
            # Asegurarse de que op_id esté en los datos
            issue_data['orden_produccion_id'] = op_id

            # Intentar crear (insertar)
            result = self.create(issue_data)

            if not result.get('success') and '23505' in str(result.get('error')):
                # Error 23505: Violación de restricción única (ya existe)
                logger.warning(f"Issue para OP {op_id} ya existe. Actualizando...")

                # Quitar campos de creación para no sobrescribir
                issue_data.pop('created_at', None)
                issue_data['updated_at'] = datetime.now().isoformat()

                # Actualizar el registro existente
                update_result = self.db.table(self.get_table_name()) \
                                    .update(self._prepare_data_for_db(issue_data)) \
                                    .eq('orden_produccion_id', op_id) \
                                    .execute()

                if update_result.data:
                    return {'success': True, 'data': update_result.data[0]}
                else:
                    return {'success': False, 'error': f"No se pudo actualizar el issue para OP {op_id}."}

            return result # Devolver el resultado de la creación original

        except Exception as e:
            logger.error(f"Error en create_or_update_by_op_id para OP {op_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}