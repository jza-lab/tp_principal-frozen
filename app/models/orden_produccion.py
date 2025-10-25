from app.models.base_model import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from app.utils import estados
# Importamos el modelo de Pedido para poder invocar su lógica
from app.models.pedido import PedidoModel

logger = logging.getLogger(__name__)

class OrdenProduccionModel(BaseModel):
    """
    Modelo para gestionar las operaciones de la tabla `ordenes_produccion` en la base de datos."""

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla de la base de datos."""
        return 'ordenes_produccion'

    def _traducir_estado_a_int(self, record: Dict) -> Dict:
        """Traduce el estado de cadena (DB) a entero (lógica) para un registro."""
        if record and 'estado' in record and isinstance(record['estado'], str):
            record['estado'] = estados.traducir_a_int(record['estado'])
        return record

    def _traducir_lista_estados_a_int(self, records: List[Dict]) -> List[Dict]:
        """Aplica la traducción de estado a una lista de registros."""
        return [self._traducir_estado_a_int(record) for record in records]

    def _traducir_estado_a_cadena(self, record: Dict) -> Dict:
        """Traduce el estado de entero (lógica) a cadena (DB) para un registro."""
        if record and 'estado' in record and isinstance(record['estado'], int):
            record['estado'] = estados.traducir_a_cadena(record['estado'])
        return record

    def cambiar_estado(self, orden_id: int, nuevo_estado: int, observaciones: Optional[str] = None) -> Dict:
        """
        Cambia el estado de una orden de producción, actualiza fechas clave
        (incluyendo fecha_inicio real al entrar en línea por primera vez) y el estado
        de los items de pedido asociados.
        """
        try:
            nuevo_estado_str = estados.traducir_a_cadena(nuevo_estado)
            update_data = {'estado': nuevo_estado_str}
            if observaciones:
                update_data['observaciones'] = observaciones

            now_iso = datetime.now().isoformat()

            estados_produccion_activa = [
                estados.traducir_a_int('EN_LINEA_1'), 
                estados.traducir_a_int('EN_LINEA_2'), 
                estados.traducir_a_int('EN_EMPAQUETADO'), 
                estados.traducir_a_int('CONTROL_DE_CALIDAD')
            ]

            if nuevo_estado in estados_produccion_activa:
                orden_actual_res = self.find_by_id(orden_id, 'id')
                if orden_actual_res.get('success') and orden_actual_res.get('data') and not orden_actual_res['data'].get('fecha_inicio'):
                    update_data['fecha_inicio'] = now_iso
                    logger.info(f"Registrando inicio real de producción para OP {orden_id} a las {now_iso}")

            elif nuevo_estado == estados.COMPLETADA:
                update_data['fecha_fin'] = now_iso

            elif nuevo_estado == estados.APROBADA:
                fecha_aprobacion = datetime.now()
                update_data['fecha_aprobacion'] = fecha_aprobacion.isoformat()

            update_result = self.update(id_value=orden_id, data=update_data, id_field='id')
            if not update_result.get('success'):
                logger.error(f"Fallo al actualizar OP {orden_id} a estado {nuevo_estado_str}: {update_result.get('error')}")
                return update_result

            nuevo_estado_item_int = None
            if nuevo_estado in estados_produccion_activa:
                nuevo_estado_item_int = estados.EN_PRODUCCION
            elif nuevo_estado == estados.COMPLETADA:
                nuevo_estado_item_int = estados.ALISTADO

            if nuevo_estado_item_int is not None:
                nuevo_estado_item_str = estados.traducir_a_cadena(nuevo_estado_item_int)
                try:
                    items_result = self.db.table('pedido_items').select('id, pedido_id').eq('orden_produccion_id', orden_id).execute()

                    if items_result.data:
                        self.db.table('pedido_items').update({'estado': nuevo_estado_item_str}).eq('orden_produccion_id', orden_id).execute()
                        logger.info(f"Items del pedido asociados a OP {orden_id} actualizados a {nuevo_estado_item_str}.")

                        # Obtener IDs únicos de los pedidos afectados
                        pedidos_ids_afectados = {item['pedido_id'] for item in items_result.data}

                        # Instanciar PedidoModel y actualizar estado agregado de cada pedido
                        pedido_model = PedidoModel()
                        for pedido_id in pedidos_ids_afectados:
                            # Este método debería recalcular el estado general del pedido
                            pedido_model.actualizar_estado_agregado(pedido_id)
                            logger.info(f"Estado agregado del Pedido {pedido_id} actualizado.")

                except Exception as e_cascade:
                    # Si falla la cascada, la OP ya cambió de estado. Loggeamos el error pero no revertimos.
                    logger.error(f"Error en actualización cascada para OP {orden_id} -> Pedidos: {e_cascade}", exc_info=True)
                    # Podrías añadir una advertencia al resultado si lo deseas
                    update_result['warning'] = "Estado de OP actualizado, pero falló la actualización de pedidos asociados."


            return update_result # Devuelve el resultado del update principal de la OP

        except Exception as e:
            logger.error(f"Error crítico cambiando estado de la orden {orden_id} a {nuevo_estado}: {e}", exc_info=True)
            return {'success': False, 'error': f"Error interno: {str(e)}"}

    def get_all_enriched(self, filtros: Optional[Dict] = None) -> Dict:
        """
        Obtiene todas las órdenes de producción con datos enriquecidos
        de tablas relacionadas y un manejo de filtros avanzado.
        """
        try:
            # Base query selecting related data
            query = self.db.table(self.get_table_name()).select(
                "*, productos(nombre, unidad_medida), "
                "creador:usuario_creador_id(nombre, apellido), "
                "supervisor:supervisor_responsable_id(nombre, apellido), "
                "operario:operario_asignado_id(nombre, apellido)"
            )

            # Apply filters dynamically
            if filtros:
                for key, value in filtros.items():
                    if value is None:
                        continue

                    # Handle tuple operators like ('in', [...]) or ('not.in', [...])
                    if isinstance(value, tuple) and len(value) == 2:
                        operator, filter_value = value
                        if operator.lower() == 'in':
                            query = query.in_(key, filter_value)
                        elif operator.lower() == 'not.in':
                            # Implement specific logic for 'not in' based on your DB library
                            # Example for some libraries (might need adjustment):
                            # query = query.not_.in_(key, filter_value)
                            logger.warning(f"Operator 'not.in' for key '{key}' not fully implemented yet.")
                            pass # Add implementation or filter later in Python if needed

                    # Handle specific date range keys
                    elif key == 'fecha_planificada_desde':
                        query = query.gte('fecha_planificada', value)
                    elif key == 'fecha_planificada_hasta':
                        query = query.lte('fecha_planificada', value)
                    elif key == 'fecha_inicio_planificada_desde':
                        query = query.gte('fecha_inicio_planificada', value)
                    elif key == 'fecha_inicio_planificada_hasta':
                        query = query.lte('fecha_inicio_planificada', value)

                        # --- AÑADIR/VERIFICAR ESTOS ELIF ---
                    elif key == 'fecha_meta_desde':
                        query = query.gte('fecha_meta', value)
                    elif key == 'fecha_meta_hasta':
                        query = query.lte('fecha_meta', value)
                    # --- FIN ---

                    # Default to equality filter
                    else:
                        query = query.eq(key, value)

            # Apply ordering (e.g., for weekly view and general listing)
            query = query.order("fecha_inicio_planificada", desc=False).order("id", desc=True)

            # Execute the query
            result = query.execute()

            logger.debug(f"RAW DATA FROM DB (get_all_enriched): {result.data}")

            # Process and flatten the results
            if result.data:
                processed_data = []
                for item in result.data:
                    # Flatten product info
                    # --- AÑADIR LÓGICA PARA 'unidad_medida' ---
                    if item.get('productos'):
                        producto_info = item.pop('productos')
                        item['producto_nombre'] = producto_info.get('nombre','N/A')
                        item['producto_presentacion'] = producto_info.get('presentacion') # Mantener por si acaso
                        item['producto_unidad_medida'] = producto_info.get('unidad_medida') # <-- AÑADIDO
                    else:
                        item['producto_nombre'] = 'N/A'
                        item['producto_presentacion'] = None
                        item['producto_unidad_medida'] = None # <-- AÑADIDO
                    # --- FIN LÓGICA AÑADIDA ---

                    # Flatten creator info
                    if item.get('creador'):
                        creador_info = item.pop('creador')
                        item['creador_nombre'] = f"{creador_info.get('nombre', '')} {creador_info.get('apellido', '')}".strip()
                    else:
                        item['creador_nombre'] = 'No asignado'

                    # Flatten supervisor info
                    if item.get('supervisor'):
                        supervisor_info = item.pop('supervisor')
                        item['supervisor_nombre'] = f"{supervisor_info.get('nombre', '')} {supervisor_info.get('apellido', '')}".strip()
                    else:
                        item['supervisor_nombre'] = 'Sin asignar' # Or None if preferred

                    # Flatten operario info
                    if item.get('operario'):
                        operario_info = item.pop('operario')
                        item['operario_nombre'] = f"{operario_info.get('nombre', '')} {operario_info.get('apellido', '')}".strip()
                    else:
                        item['operario_nombre'] = None # Explicitly None if not assigned

                    processed_data.append(item)

                op_ids = [op['id'] for op in processed_data]
                pedidos_por_op = {}

                if op_ids:
                    # Obtenemos todos los items de pedido vinculados a estas OP, incluyendo los datos del pedido.
                    items_result = self.db.table('pedido_items').select(
                        'orden_produccion_id, pedido:pedidos!pedido_items_pedido_id_fkey(id, nombre_cliente, estado)'
                    ).in_('orden_produccion_id', op_ids).execute()

                    if items_result.data:
                        for item in items_result.data:
                            op_id = item['orden_produccion_id']
                            if op_id not in pedidos_por_op:
                                pedidos_por_op[op_id] = []

                            pedido_info = item.get('pedido')
                            if pedido_info:
                                # Evitamos duplicados si múltiples items de un mismo pedido apuntan a la misma OP
                                if not any(p['id'] == pedido_info['id'] for p in pedidos_por_op[op_id]):
                                    pedidos_por_op[op_id].append(pedido_info)

                # Adjuntamos la lista de pedidos (o una lista vacía) a cada OP
                for op in processed_data:
                    op['pedidos_asociados'] = pedidos_por_op.get(op['id'], [])

                # Traducir estados a enteros
                processed_data = self._traducir_lista_estados_a_int(processed_data)
                return {'success': True, 'data': processed_data}
            else:
                # No data found, but the query was successful
                return {'success': True, 'data': []}

        except Exception as e:
            # Log the full traceback for better debugging
            logger.error(f"Error al obtener órdenes enriquecidas: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_one_enriched(self, orden_id: int) -> Dict:
        """
        Obtiene una orden de producción específica con datos enriquecidos.
        """
        try:
            # .maybe_single() ejecuta la consulta y devuelve un solo dict o None
            response = self.db.table(self.get_table_name()).select(
                "*, productos(nombre, descripcion, unidad_medida), recetas(id, descripcion, rendimiento, activa), " # Añadido unidad_medida
                "creador:usuario_creador_id(nombre, apellido), "
                "supervisor:supervisor_responsable_id(nombre, apellido), "
                "operario:operario_asignado_id(nombre, apellido)" # <-- Incluir operario
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
                    producto_info = item.pop('productos')
                    item['producto_nombre'] = producto_info.get('nombre', 'N/A')
                    item['producto_descripcion'] = producto_info.get('descripcion', 'N/A')
                    item['producto_unidad_medida'] = producto_info.get('unidad_medida') # ¿Está esta línea?
                else:
                     item['producto_nombre'] = 'N/A' # Añadir fallback
                     item['producto_descripcion'] = 'N/A' # Añadir fallback
                     item['producto_unidad_medida'] = None # Asegurar que existe aunque sea None
                # --- FIN VERIFICACIÓN ---

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

                # --- AÑADIR ESTE BLOQUE PARA EL OPERARIO ---
                if item.get('operario'):
                    operario_info = item.pop('operario')
                    item['operario_nombre'] = f"{operario_info.get('nombre', '')} {operario_info.get('apellido', '')}".strip()
                    # Si el nombre resultante está vacío, poner 'No asignado'
                    if not item['operario_nombre']:
                         item['operario_nombre'] = 'No asignado'
                else:
                    item['operario_nombre'] = 'No asignado'
                # --- FIN DEL BLOQUE AÑADIDO ---

                # Traducir estado a entero
                item = self._traducir_estado_a_int(item)
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
                # Traducir estados a enteros
                translated_data = self._traducir_lista_estados_a_int(result.data)
                return {'success': True, 'data': translated_data}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error al buscar órdenes por IDs: {op_ids}. Error: {str(e)}")
            return {'success': False, 'error': str(e)}