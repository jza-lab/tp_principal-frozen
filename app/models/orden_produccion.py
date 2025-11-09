from app.models.base_model import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
logger = logging.getLogger(__name__)

class OrdenProduccionModel(BaseModel):
    """
    Modelo para gestionar las operaciones de la tabla `ordenes_produccion` en la base de datos."""

    def get_table_name(self) -> str:
        """Devuelve el nombre de la tabla de la base de datos."""
        return 'ordenes_produccion'

    def cambiar_estado(self, orden_id: int, nuevo_estado: str, observaciones: Optional[str] = None, extra_data: Optional[Dict] = None) -> Dict:
        """
        Cambia el estado de una orden de producción y actualiza las fechas clave.
        La lógica de negocio compleja (como actualizar pedidos) se maneja en el controlador.
        """
        try:
            # 1. Preparar los datos base para la actualización
            update_data = {'estado': nuevo_estado}
            if observaciones:
                update_data['observaciones'] = observaciones

            if extra_data:
                update_data.update(extra_data)

            now_iso = datetime.now().isoformat()

            # --- LÓGICA DE FECHAS MEJORADA ---
            if nuevo_estado in ['EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'CONTROL_DE_CALIDAD']:
                orden_actual_res = self.find_by_id(orden_id, 'id')
                if orden_actual_res.get('success') and orden_actual_res.get('data') and not orden_actual_res['data'].get('fecha_inicio'):
                    update_data['fecha_inicio'] = now_iso
                    logger.info(f"Registrando inicio real de producción para OP {orden_id} a las {now_iso}")

            elif nuevo_estado == 'COMPLETADA':
                update_data['fecha_fin'] = now_iso

            elif nuevo_estado == 'APROBADA':
                fecha_aprobacion = datetime.now()
                update_data['fecha_aprobacion'] = fecha_aprobacion.isoformat()

            # 2. Actualizar la orden de producción en la base de datos
            update_result = self.update(id_value=orden_id, data=update_data, id_field='id')
            if not update_result.get('success'):
                logger.error(f"Fallo al actualizar OP {orden_id} a estado {nuevo_estado}: {update_result.get('error')}")

            return update_result

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
                "operario:operario_asignado_id(nombre, apellido), "
                "aprobador:aprobador_calidad_id(nombre, apellido)"
            )

            # Apply filters dynamically
            if filtros:
                # --- INICIO DE LA CORRECCIÓN (MAPA DE OPERADORES) ---
                # Definimos el mapa de operadores de Supabase/PostgREST
                op_map = {
                    'eq': query.eq, 'gt': query.gt, 'gte': query.gte,
                    'lt': query.lt, 'lte': query.lte, 'in_': query.in_,
                    'ilike': query.ilike,
                    'neq': query.neq
                }
                # --- FIN DE LA CORRECCIÓN ---

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
                        continue # <-- Importante: saltar al siguiente filtro

                    # Handle specific date range keys
                    elif key == 'fecha_planificada_desde':
                        query = query.gte('fecha_planificada', value)
                        continue # <-- Importante
                    elif key == 'fecha_planificada_hasta':
                        query = query.lte('fecha_planificada', value)
                        continue # <-- Importante
                    elif key == 'fecha_inicio_planificada_desde':
                        query = query.gte('fecha_inicio_planificada', value)
                        continue # <-- Importante
                    elif key == 'fecha_inicio_planificada_hasta':
                        query = query.lte('fecha_inicio_planificada', value)
                        continue # <-- Importante
                    elif key == 'fecha_meta_desde':
                        query = query.gte('fecha_meta', value)
                        continue # <-- Importante
                    elif key == 'fecha_meta_hasta':
                        query = query.lte('fecha_meta', value)
                        continue # <-- Importante

                    # --- INICIO DE LA CORRECCIÓN (LÓGICA DE OPERADORES) ---
                    # Revisar si la clave termina con un operador (ej: 'campo_nombre_neq')
                    parts = key.split('_')
                    operator = parts[-1]

                    if len(parts) > 1 and operator in op_map:
                        column_name = '_'.join(parts[:-1])
                        # Usar el operador del mapa
                        # (Nota: 'in' se maneja como 'in_' en el mapa por ser palabra clave)
                        if operator == 'in':
                            query = op_map['in_'](column_name, value)
                        else:
                            query = op_map[operator](column_name, value)

                        continue # <-- Importante: saltar al siguiente filtro
                    # --- FIN DE LA CORRECCIÓN ---

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

                    # Flatten aprobador info
                    if item.get('aprobador'):
                        aprobador_info = item.pop('aprobador')
                        item['aprobador_calidad_nombre'] = f"{aprobador_info.get('nombre', '')} {aprobador_info.get('apellido', '')}".strip()
                    else:
                        item['aprobador_calidad_nombre'] = None

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
                "operario:operario_asignado_id(nombre, apellido), " # <-- Incluir operario
                "aprobador:aprobador_calidad_id(nombre, apellido)"
            ).eq("id", orden_id).maybe_single().execute()

            item = response.data
            FORMATO_SALIDA = "%Y-%m-%d %H:%M"

            if item:
                # --- Lógica para obtener supervisor de calidad por separado ---
                if item.get('supervisor_calidad_id'):
                    sv_calidad_res = self.db.table('usuarios').select('nombre, apellido').eq('id', item['supervisor_calidad_id']).single().execute()
                    if sv_calidad_res.data:
                        sv_info = sv_calidad_res.data
                        item['supervisor_calidad_nombre'] = f"{sv_info.get('nombre', '')} {sv_info.get('apellido', '')}".strip()
                    else:
                        item['supervisor_calidad_nombre'] = 'No encontrado'
                else:
                    item['supervisor_calidad_nombre'] = 'No asignado'
                # --- Fin de la nueva lógica ---

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

                if item.get('aprobador'):
                    aprobador_info = item.pop('aprobador')
                    item['aprobador_calidad_nombre'] = f"{aprobador_info.get('nombre', '')} {aprobador_info.get('apellido', '')}".strip()
                else:
                    item['aprobador_calidad_nombre'] = None

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

    def get_for_kanban_hoy(self, filtros_operario: Optional[Dict] = None) -> Dict:
        """
        Obtiene las OPs para el Kanban. Incluye OPs en estados estándar
        y aquellas pausadas que tienen un traspaso de turno pendiente.
        """
        try:
            # 1. Obtener IDs de OPs con traspasos de turno pendientes
            traspasos_pendientes_res = self.db.schema('mes_kanban').table('traspasos_turno').select('orden_produccion_id').is_('usuario_entrante_id', None).execute()
            op_ids_con_traspaso = []
            if traspasos_pendientes_res.data:
                op_ids_con_traspaso = {item['orden_produccion_id'] for item in traspasos_pendientes_res.data}

            # 2. Definir los estados base para la vista Kanban
            estados_kanban = [
                'EN_ESPERA', 'LISTA_PARA_PRODUCIR', 'EN_LINEA_1', 'EN_LINEA_2',
                'EN_EMPAQUETADO', 'EN_PROCESO', 'CONTROL_DE_CALIDAD', 'COMPLETADA', 'PAUSADA'
            ]
            # Normalizar para la base de datos (algunos tienen espacios)
            estados_kanban_db = list(set([e.replace('_', ' ') for e in estados_kanban] + estados_kanban))


            # 3. Construir y ejecutar la consulta base
            query = self.db.table(self.get_table_name()).select(
                "*, productos(nombre, unidad_medida), "
                "operario:operario_asignado_id(nombre, apellido), "
                "aprobador:aprobador_calidad_id(nombre, apellido)"
            ).in_('estado', estados_kanban_db)

            result = query.execute()

            if not result.data:
                return {'success': True, 'data': []}

            # 4. Procesar y filtrar en Python para lógica compleja
            ordenes_finales = []
            all_data = result.data

            for item in all_data:
                # Lógica de filtrado para Operarios
                if filtros_operario and filtros_operario.get('rol') == 'OPERARIO':
                    usuario_id = filtros_operario.get('usuario_id')
                    estado_actual = item.get('estado')
                    es_suya = item.get('operario_asignado_id') == usuario_id

                    # Un operario solo ve OPs 'EN ESPERA', 'LISTA PARA PRODUCIR', las que están 'EN PROCESO' asignadas a él,
                    # y las pausadas por traspaso que están listas para ser tomadas.
                    if not (estado_actual in ['EN_ESPERA', 'LISTA PARA PRODUCIR', 'LISTA_PARA_PRODUCIR'] or
                            (estado_actual == 'EN_PROCESO' and es_suya) or
                            (item['id'] in op_ids_con_traspaso and estado_actual == 'PAUSADA')):
                        continue # Si no cumple, la salta

                # Lógica de visualización para traspasos
                # Si una orden está pausada Y tiene un traspaso pendiente, se muestra como 'LISTA PARA PRODUCIR'
                if item.get('id') in op_ids_con_traspaso and item.get('estado') == 'PAUSADA':
                    item['estado'] = 'LISTA PARA PRODUCIR'

                # Excluir las órdenes pausadas que NO son por traspaso del Kanban
                elif item.get('estado') == 'PAUSADA':
                    continue

                # Aplanar datos para la vista
                if item.get('productos'):
                    item['producto_nombre'] = item.pop('productos').get('nombre', 'N/A')
                else:
                    item['producto_nombre'] = 'N/A'

                if item.get('operario'):
                    operario = item.pop('operario')
                    item['operario_nombre'] = f"{operario.get('nombre', '')} {operario.get('apellido', '')}".strip()
                else:
                    item['operario_nombre'] = None

                if item.get('aprobador'):
                    aprobador = item.pop('aprobador')
                    item['aprobador_calidad_nombre'] = f"{aprobador.get('nombre', '')} {aprobador.get('apellido', '')}".strip()
                else:
                    item['aprobador_calidad_nombre'] = None

                ordenes_finales.append(item)

            # 5. Enriquecer con pedidos asociados (solo para las órdenes finales)
            op_ids_finales = [op['id'] for op in ordenes_finales]
            pedidos_por_op = {}
            if op_ids_finales:
                items_result = self.db.table('pedido_items').select(
                    'orden_produccion_id, pedido:pedidos!pedido_items_pedido_id_fkey(id)'
                ).in_('orden_produccion_id', op_ids_finales).execute()

                if items_result.data:
                    for item in items_result.data:
                        op_id = item['orden_produccion_id']
                        if op_id not in pedidos_por_op: pedidos_por_op[op_id] = []
                        pedido_info = item.get('pedido')
                        if pedido_info and not any(p['id'] == pedido_info['id'] for p in pedidos_por_op.get(op_id, [])):
                            pedidos_por_op[op_id].append(pedido_info)

            for op in ordenes_finales:
                op['pedidos_asociados'] = pedidos_por_op.get(op['id'], [])

            return {'success': True, 'data': ordenes_finales}

        except Exception as e:
            logger.error(f"Error en get_for_kanban_hoy: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_all_for_planificacion(self, fecha_fin_horizonte, fecha_inicio_semanal, fecha_fin_semanal) -> Dict:
        """
        Obtiene todas las OPs para la vista de planificación usando una consulta OR.
        """
        try:
            # Condición 1: OPs PENDIENTES dentro del horizonte del MPS
            filtro_pendientes = f"and(estado.eq.PENDIENTE,fecha_meta.lte.{fecha_fin_horizonte.isoformat()})"

            # Condición 2: OPs PLANIFICADAS que son visibles en el calendario semanal
            estados_planificados = ['EN ESPERA', 'LISTA PARA PRODUCIR', 'EN_LINEA_1', 'EN_LINEA_2', 'EN_EMPAQUETADO', 'CONTROL_DE_CALIDAD']
            estados_formateados = ','.join([f'"{estado}"' for estado in estados_planificados])
            filtro_planificadas = f"and(estado.in.({estados_formateados}),fecha_inicio_planificada.gte.{fecha_inicio_semanal.isoformat()},fecha_inicio_planificada.lte.{fecha_fin_semanal.isoformat()})"

            # Combinar con OR
            query_filter = f"or({filtro_pendientes},{filtro_planificadas})"

            response = self.db.table(self.get_table_name()).select(
                "*, productos(nombre, unidad_medida), "
                "creador:usuario_creador_id(nombre, apellido), "
                "supervisor:supervisor_responsable_id(nombre, apellido), "
                "operario:operario_asignado_id(nombre, apellido)"
            ).or_(query_filter).execute()

            if response.data:
                # Reutilizar la lógica de aplanamiento de get_all_enriched
                # (Esta parte se puede refactorizar a un helper si se repite mucho)
                processed_data = []
                for item in response.data:
                    if item.get('productos'):
                        item['producto_nombre'] = item.pop('productos').get('nombre', 'N/A')
                    if item.get('creador'):
                        creador = item.pop('creador')
                        item['creador_nombre'] = f"{creador.get('nombre','')} {creador.get('apellido','')}".strip()
                    # ... aplanar otros campos como supervisor, operario ...
                    processed_data.append(item)
                return {'success': True, 'data': processed_data}

            return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error en get_all_for_planificacion: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
