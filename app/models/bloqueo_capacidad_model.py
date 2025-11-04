import logging
from app.models.base_model import BaseModel
from typing import Dict

logger = logging.getLogger(__name__)

class BloqueoCapacidadModel(BaseModel):
    """
    Modelo para gestionar los bloqueos de capacidad (mantenimiento)
    en la tabla 'bloqueos_capacidad'.
    """

    def get_table_name(self) -> str:
        return 'bloqueos_capacidad'


    def get_all_with_details(self) -> Dict:
        """
        Obtiene todos los bloqueos programados, uniendo el nombre
        del centro de trabajo (Línea) para mostrar en la tabla de configuración.

        Requerido por: PlanificacionController.obtener_datos_configuracion()

        """
        try:
            # Realiza un JOIN con la tabla centro_trabajo para obtener el nombre
            # La sintaxis "centro_trabajo!inner(id, nombre)" es específica de Supabase
            query = self.db.table(self.table_name) \
                          .select("*, CentrosTrabajo!inner(id, nombre)") \
                          .order("fecha", desc=True) # Mostrar los más recientes primero

            response = query.execute()

            data = []
            # Aplanar la respuesta para que sea más fácil de usar en el template
            for item in response.data:
                centro_data = item.pop('centro_trabajo', {})
                item['nombre_centro'] = centro_data.get('nombre', 'N/A')
                data.append(item)

            return {'success': True, 'data': data}

        except Exception as e:
            logger.error(f"Error en get_all_with_details (BloqueoCapacidadModel): {e}", exc_info=True)
            return {'success': False, 'error': f"Error al obtener bloqueos con detalle: {str(e)}"}

    # ---
    # NOTA: Los métodos create(), find_all() y delete() son heredados
    # de BaseModel, por lo que no necesitamos re-implementarlos aquí.
    # El controlador los llamará directamente:
    # - find_all()
    # - create()
    # - delete()
    # ---