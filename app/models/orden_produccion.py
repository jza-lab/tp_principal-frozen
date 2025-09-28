from app.models.base_model import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class OrdenProduccionModel(BaseModel):
    """
    Modelo para gestionar las operaciones de la tabla `ordenes_produccion` en la base de datos."""

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla de la base de datos."""
        return 'ordenes_produccion'

    def cambiar_estado(self, orden_id: int, nuevo_estado: str, observaciones: Optional[str] = None) -> Dict:
        """
        Cambia el estado de una orden de producción y actualiza fechas si es necesario.
        """
        try:
            update_data = {'estado': nuevo_estado}
            if observaciones:
                update_data['observaciones'] = observaciones

            if nuevo_estado == 'EN_PROCESO':
                update_data['fecha_inicio'] = datetime.now().isoformat()
            elif nuevo_estado == 'COMPLETADA':
                update_data['fecha_fin'] = datetime.now().isoformat()

            return self.update(id_value=orden_id, data=update_data, id_field='id')
        except Exception as e:
            logger.error(f"Error cambiando estado de la orden {orden_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_all_enriched(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Obtiene todas las órdenes de producción con datos enriquecidos de tablas relacionadas
        (productos, usuarios, etc.) utilizando el cliente de Supabase.
        """
        try:
            # El string de select indica que queremos todos los campos de ordenes_produccion,
            # y de las tablas relacionadas 'productos' y 'usuarios', traemos el campo 'nombre'.
            # Supabase infiere las relaciones por las Foreign Keys.
            query = self.db.table(self.table_name).select(
                "*, productos(nombre), usuarios(nombre)"
            )
            
            # Aplicar filtros
            if filtros:
                for key, value in filtros.items():
                    if value is not None:
                        query = query.eq(key, value)
            
            # Ordenar
            query = query.order("fecha_planificada", desc=True).order("id", desc=True)

            result = query.execute()

            if result.data:
                # Aplanar la respuesta para que coincida con lo que espera la vista/template
                processed_data = []
                for item in result.data:
                    if item.get('productos'):
                        item['producto_nombre'] = item.pop('productos')['nombre']
                    else:
                        item['producto_nombre'] = 'N/A'
                    
                    if item.get('usuarios'):
                        item['operario_nombre'] = item.pop('usuarios')['nombre']
                    else:
                        item['operario_nombre'] = 'No asignado'
                    
                    processed_data.append(item)
                return {'success': True, 'data': processed_data}
            else:
                # Si no hay datos, devolvemos una lista vacía, lo cual no es un error.
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error al obtener órdenes enriquecidas: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_one_enriched(self, orden_id: int) -> Dict:
        """
        Obtiene una orden de producción específica con datos enriquecidos.
        """
        try:
            # .maybe_single() ejecuta la consulta y devuelve un solo dict o None
            item = self.db.table(self.table_name).select(
                "*, productos(nombre, descripcion), recetas(codigo), usuarios(nombre)"
            ).eq("id", orden_id).maybe_single()
            
            if item:
                # Aplanar la respuesta
                if item.get('productos'):
                    item['producto_nombre'] = item['productos'].get('nombre', 'N/A')
                    item['producto_descripcion'] = item['productos'].get('descripcion', 'N/A')
                    item.pop('productos')
                
                if item.get('recetas'):
                    item['receta_codigo'] = item['recetas'].get('codigo', 'N/A')
                    item.pop('recetas')

                if item.get('usuarios'):
                    item['operario_nombre'] = item['usuarios'].get('nombre', 'No asignado')
                    item.pop('usuarios')
                
                return {'success': True, 'data': item}
            else:
                return {'success': False, 'error': f'Orden con id {orden_id} no encontrada.'}

        except Exception as e:
            logger.error(f"Error al obtener la orden enriquecida {orden_id}: {str(e)}")
            return {'success': False, 'error': str(e)}