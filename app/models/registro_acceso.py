from app.models.base_model import BaseModel
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class RegistroAccesoModel(BaseModel):
    def get_table_name(self):
        return 'registros_acceso'

    def obtener_actividad_filtrada(self, filtros: dict) -> Dict:
        """
        Obtiene la actividad de acceso web (inicios y cierres de sesión) según los filtros proporcionados.
        Filtros: 'fecha_desde', 'fecha_hasta', 'sector_id'.
        """
        try:
            # Base de la consulta
            query = self.db.table(self.get_table_name()).select(
                '*, usuario:usuarios(id, nombre, apellido, legajo, roles(nombre), sectores:usuario_sectores(sectores(nombre)))'
            )

            # 1. Filtrar por sector primero si está presente
            if filtros and filtros.get('sector_id'):
                user_ids_in_sector_res = self.db.table('usuario_sectores').select(
                    'usuario_id'
                ).eq('sector_id', filtros['sector_id']).execute()
                
                if not user_ids_in_sector_res.data:
                    return {'success': True, 'data': []}
                
                user_ids = [item['usuario_id'] for item in user_ids_in_sector_res.data]
                query = query.in_('usuario_id', user_ids)

            # 2. Aplicar filtros de fecha
            if filtros and filtros.get('fecha_desde'):
                query = query.gte('fecha_hora', f"{filtros['fecha_desde']}T00:00:00")
            if filtros and filtros.get('fecha_hasta'):
                query = query.lte('fecha_hora', f"{filtros['fecha_hasta']}T23:59:59")

            # 3. Ejecutar la consulta final
            response = query.order('fecha_hora', desc=True).execute()

            return {'success': True, 'data': response.data or []}
        except Exception as e:
            logger.error(f"Error obteniendo la actividad de acceso web filtrada: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
