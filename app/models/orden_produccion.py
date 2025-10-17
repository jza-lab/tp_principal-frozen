from app.models.base_model import BaseModel
from typing import Dict, Any, Optional, List
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
        Cambia el estado de una orden de producción, actualiza fechas clave y el estado
        de los items de pedido asociados.
        """
        try:
            # 1. Preparar los datos para la actualización
            update_data = {'estado': nuevo_estado}
            if observaciones:
                update_data['observaciones'] = observaciones

            now = datetime.now().isoformat()

            # --- LÓGICA DE FECHAS MEJORADA ---
            # Si la orden entra en una etapa de producción activa por primera vez
            if nuevo_estado in ['EN_PROCESO', 'EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'CONTROL_DE_CALIDAD']:
                # Verificamos si la fecha_inicio ya fue establecida para no sobrescribirla
                orden_actual_res = self.find_by_id(orden_id, 'id')
                if orden_actual_res.get('success') and not orden_actual_res['data'].get('fecha_inicio'):
                    update_data['fecha_inicio'] = now

            # Si la orden se completa, registramos la fecha de fin
            elif nuevo_estado in ['COMPLETADA', 'FINALIZADA']:
                update_data['fecha_fin'] = now

            # Mantenemos la lógica para la fecha de aprobación
            elif nuevo_estado == 'APROBADA':
                fecha_aprobacion = datetime.now()
                fecha_fin_esperada = fecha_aprobacion + timedelta(weeks=1)
                update_data['fecha_aprobacion'] = fecha_aprobacion.isoformat()
                update_data['fecha_fin_estimada'] = fecha_fin_esperada.isoformat()
            # --- FIN DE LA LÓGICA DE FECHAS ---

            # 2. Actualizar la orden de producción en la base de datos
            update_result = self.update(id_value=orden_id, data=update_data, id_field='id')
            if not update_result.get('success'):
                return update_result

            # 3. Lógica de actualización en cascada para los pedidos (esta parte no cambia)
            nuevo_estado_item = None
            if nuevo_estado in ['EN_PROCESO', 'EN_LINEA_1', 'EN_LINEA_2']:
                nuevo_estado_item = 'EN_PRODUCCION'
            elif nuevo_estado in ['COMPLETADA', 'FINALIZADA']:
                nuevo_estado_item = 'ALISTADO'

            if nuevo_estado_item:
                items_result = self.db.table('pedido_items').select('id, pedido_id').eq('orden_produccion_id', orden_id).execute()

                if items_result.data:
                    self.db.table('pedido_items').update({'estado': nuevo_estado_item}).eq('orden_produccion_id', orden_id).execute()
                    pedidos_ids_afectados = {item['pedido_id'] for item in items_result.data}

                    pedido_model = PedidoModel()
                    for pedido_id in pedidos_ids_afectados:
                        pedido_model.actualizar_estado_agregado(pedido_id)

            return update_result
        except Exception as e:
            logger.error(f"Error cambiando estado de la orden {orden_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_all_enriched(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Obtiene todas las órdenes de producción con datos enriquecidos de tablas relacionadas
        y un manejo de filtros avanzado.
        """
        try:
            query = self.db.table(self.table_name).select(
                "*, productos(nombre), "
                "creador:usuario_creador_id(nombre, apellido), "
                "supervisor:supervisor_responsable_id(nombre, apellido)"
            )

            # ... (toda tu lógica de filtros se mantiene igual) ...
            if filtros:
                for key, value in filtros.items():
                    if value is None:
                        continue
                    if isinstance(value, tuple) and len(value) == 2:
                        operator, filter_value = value
                        if operator.lower() == 'in':
                            query = query.in_(key, filter_value)
                    elif key == 'fecha_planificada_desde':
                        query = query.gte('fecha_planificada', value)
                    elif key == 'fecha_planificada_hasta':
                        query = query.lte('fecha_planificada', value)
                    else:
                        query = query.eq(key, value)

            query = query.order("fecha_planificada", desc=True).order("id", desc=True)
            result = query.execute()

            # --- LÍNEA DE DEPURACIÓN AÑADIDA ---
            # Esta línea imprimirá en tu consola lo que la base de datos devuelve
            logger.debug(f"RAW DATA FROM DB FOR KANBAN: {result.data}")
            # ------------------------------------

            if result.data:
                processed_data = []
                # ... (el resto de tu método para procesar los datos sigue igual) ...
                for item in result.data:
                    if item.get('productos'):
                        item['producto_nombre'] = item['productos'].get('nombre', 'N/A')
                    else:
                        item['producto_nombre'] = 'Producto no definido'
                    if 'productos' in item: item.pop('productos')
                    # ... etc ...
                    processed_data.append(item)
                return {'success': True, 'data': processed_data}
            else:
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
                "*, productos(nombre, descripcion), recetas(id, descripcion, rendimiento, activa), "
                "creador:usuario_creador_id(nombre, apellido), "
                "supervisor:supervisor_responsable_id(nombre, apellido)"
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

                if item.get('creador'):
                    creador_info = item.pop('creador')
                    item['creador_nombre'] = f"{creador_info.get('nombre', '')} {creador_info.get('apellido', '')}".strip()
                else:
                    item['creador_nombre'] = 'No asignado'

                if item.get('supervisor'):
                    supervisor_info = item.pop('supervisor')
                    item['supervisor_nombre'] = f"{supervisor_info.get('nombre', '')} {supervisor_info.get('apellido', '')}".strip()
                else:
                    item['supervisor_nombre'] = 'No asignado'

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
                '*, pedido_detalle:pedidos!pedido_items_pedido_id_fkey(id, nombre_cliente)'
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

    def find_by_ids(self, op_ids: List[int]) -> Dict:
        """
        Busca y devuelve múltiples órdenes de producción a partir de una lista de IDs.
        """
        try:
            if not op_ids:
                return {'success': True, 'data': []}

            result = self.db.table(self.table_name).select(
                "*" # Puedes enriquecerlo si quieres, pero para la consolidación no es necesario
            ).in_('id', op_ids).execute()

            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error al buscar órdenes por IDs: {op_ids}. Error: {str(e)}")
            return {'success': False, 'error': str(e)}