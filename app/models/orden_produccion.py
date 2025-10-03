from app.models.base_model import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
# Importamos el modelo de Pedido para poder invocar su lógica
from app.models.pedido import PedidoModel

logger = logging.getLogger(__name__)

class OrdenProduccionModel(BaseModel):
    """
    Modelo para gestionar las operaciones de la tabla `ordenes_produccion` en la base de datos."""

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla de la base de datos."""
        return 'ordenes_produccion'

    def cambiar_estado(self, orden_id: int, nuevo_estado: str, observaciones: Optional[str] = None) -> Dict:
        """
        Cambia el estado de una orden de producción y actualiza en cascada el estado
        de los items de pedido asociados y el estado agregado del pedido principal.
        """
        try:
            # 1. Actualizar la orden de producción
            update_data = {'estado': nuevo_estado}
            if observaciones:
                update_data['observaciones'] = observaciones

            if nuevo_estado == 'EN_PROCESO':
                update_data['fecha_inicio'] = datetime.now().isoformat()
            elif nuevo_estado == 'COMPLETADA':
                update_data['fecha_fin'] = datetime.now().isoformat()
            elif nuevo_estado == 'APROBADA':
                fecha_aprobacion = datetime.now()
                fecha_fin_esperada = fecha_aprobacion + timedelta(weeks=1)
                update_data['fecha_aprobacion'] = fecha_aprobacion.isoformat()
                update_data['fecha_fin_estimada'] = fecha_fin_esperada.isoformat()


            update_result = self.update(id_value=orden_id, data=update_data, id_field='id')
            if not update_result.get('success'):
                return update_result

            # 2. Lógica de actualización en cascada para los pedidos de venta
            nuevo_estado_item = None
            if nuevo_estado == 'EN_PROCESO':
                nuevo_estado_item = 'EN_PRODUCCION'
            elif nuevo_estado == 'COMPLETADA':
                nuevo_estado_item = 'ALISTADO'
            
            if nuevo_estado_item:
                # Encontrar todos los items de pedido asociados a esta orden
                items_result = self.db.table('pedido_items').select('id, pedido_id').eq('orden_produccion_id', orden_id).execute()
                
                if items_result.data:
                    # Actualizar el estado de todos los items encontrados
                    self.db.table('pedido_items').update({'estado': nuevo_estado_item}).eq('orden_produccion_id', orden_id).execute()
                    
                    # Obtener los IDs únicos de los pedidos principales para recalcular su estado
                    pedidos_ids_afectados = {item['pedido_id'] for item in items_result.data}
                    
                    pedido_model = PedidoModel()
                    for pedido_id in pedidos_ids_afectados:
                        # Llamar al método que recalculará el estado agregado del pedido
                        pedido_model.actualizar_estado_agregado(pedido_id)

            return update_result
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
                    if value is not None: #Esto es solo para planificar las cosas desde x a y fecha (?
                        if key == 'fecha_planificada_desde':
                            query = query.gte('fecha_planificada', value)
                        elif key == 'fecha_planificada_hasta':
                            query = query.lte('fecha_planificada', value)
                        else:
                            query = query.eq(key, value)
            # Ordenar
            query = query.order("fecha_planificada", desc=True).order("id", desc=True)

            result = query.execute()
            FORMATO_SALIDA = "%Y-%m-%d %H:%M"

            if result.data:
                # Aplanar la respuesta para que coincida con lo que espera la vista/template
                processed_data = []
                for item in result.data:

                    for key, value in item.items():
                        if key.startswith('fecha') and isinstance(value, str) and value:
                            try:
                                dt_object = datetime.fromisoformat(value)
                                if len(value) > 10:
                                    item[key] = dt_object.strftime(FORMATO_SALIDA)
                                else:
                                    item[key] = dt_object.strftime("%Y-%m-%d")
                            except Exception:
                                item[key] = 'Error de formato de fecha'

                    if item.get('productos'):
                        item['producto_nombre'] = item.pop('productos')['nombre']
                    else:
                        item['producto_nombre'] = 'N/A'
                    
                    if item.get('usuarios'):
                        item['creador_nombre'] = item.pop('usuarios')['nombre']
                    else:
                        item['creador_nombre'] = 'No asignado'
                    
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
            response = self.db.table(self.table_name).select(
                "*, productos(nombre, descripcion), recetas(id, descripcion, rendimiento, activa), usuarios(nombre)"
            ).eq("id", orden_id).maybe_single().execute()
           
            item = response.data
            FORMATO_SALIDA = "%Y-%m-%d %H:%M"
           
            if item:
                for key, value in item.items():
                    if key.startswith('fecha') and isinstance(value, str) and value:
                        try:
                            timestamp_str = item.get(key)

                            if timestamp_str:
                                try:
                                    dt_object = datetime.fromisoformat(timestamp_str)
                                    if len(value) > 10: #para cuando es una fecha con hora 
                                        item[key] = dt_object.strftime(FORMATO_SALIDA)
                                    else: #para cuando es solo una fecha
                                        item[key] = dt_object.strftime("%Y-%m-%d")
                                    
                                except ValueError:
                                    # En caso de que el string no sea un formato de fecha válido
                                    item[key] = 'Error de formato de fecha' 
                        except Exception:
                            item[key] = 'Error de formato de fecha'
                # Aplanar la respuesta
                if item.get('productos'):
                    item['producto_nombre'] = item['productos'].get('nombre', 'N/A')
                    item['producto_descripcion'] = item['productos'].get('descripcion', 'N/A')
                    item.pop('productos')
                
                if item.get('recetas'):
                    item['receta_codigo'] = item['recetas'].get('codigo', 'N/A')
                    item.pop('recetas')

                if item.get('usuarios'):
                    item['creador_nombre'] = item['usuarios'].get('nombre', 'No asignado')
                    item.pop('usuarios')
                
                return {'success': True, 'data': item}
            else:
                return {'success': False, 'error': f'Orden con id {orden_id} no encontrada.'}

        except Exception as e:
            logger.error(f"Error al obtener la orden enriquecida {orden_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def obtener_desglose_origen(self, orden_id: int) -> Dict:
        """
        Obtiene los items de pedido que componen una orden de producción,
        incluyendo el nombre del cliente y la cantidad de cada pedido.
        """
        try:
            result = self.db.table('pedido_items').select(
                '*, pedido:pedidos(id, nombre_cliente)'
            ).eq('orden_produccion_id', orden_id).execute()

            if result.data:
                desglose = []
                for item in result.data:
                    pedido_info = item.pop('pedido', {})
                    item['cliente_nombre'] = pedido_info.get('nombre_cliente', 'N/A')
                    item['pedido_id'] = pedido_info.get('id', 'N/A')
                    desglose.append(item)
                return {'success': True, 'data': desglose}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error obteniendo el desglose de origen para la orden {orden_id}: {str(e)}")
            return {'success': False, 'error': str(e)}