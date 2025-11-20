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
                    elif key == 'rango_fecha':
                        from datetime import datetime, timedelta
                        hoy = datetime.now()
                        if value == 'hoy':
                            inicio_dia = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
                            fin_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
                            query = query.gte('fecha_planificada', inicio_dia.isoformat())
                            query = query.lte('fecha_planificada', fin_dia.isoformat())
                        elif value == 'semana':
                            inicio_semana = hoy - timedelta(days=hoy.weekday())
                            inicio_semana = inicio_semana.replace(hour=0, minute=0, second=0, microsecond=0)
                            fin_semana = inicio_semana + timedelta(days=6)
                            fin_semana = fin_semana.replace(hour=23, minute=59, second=59, microsecond=999999)
                            query = query.gte('fecha_planificada', inicio_semana.isoformat())
                            query = query.lte('fecha_planificada', fin_semana.isoformat())
                        elif value == 'mes':
                            inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                            # This logic correctly finds the last day of the current month
                            next_month = inicio_mes.replace(day=28) + timedelta(days=4)
                            fin_mes = next_month - timedelta(days=next_month.day)
                            fin_mes = fin_mes.replace(hour=23, minute=59, second=59, microsecond=999999)
                            query = query.gte('fecha_inicio_planificada', inicio_mes.isoformat())
                            query = query.lte('fecha_inicio_planificada', fin_mes.isoformat())
                        # 'historico' doesn't apply any date filter, so we just continue
                        continue
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

                # --- INICIO DE LA LÓGICA DE HERENCIA DE PEDIDOS PARA OPS HIJAS ---

                # 1. Primera pasada: Obtener pedidos asociados directamente
                op_ids = [op['id'] for op in processed_data]
                pedidos_por_op = {}

                if op_ids:
                    items_result = self.db.table('pedido_items').select(
                        'orden_produccion_id, pedido:pedidos!pedido_items_pedido_id_fkey(id, nombre_cliente, estado)'
                    ).in_('orden_produccion_id', op_ids).execute()

                    if items_result.data:
                        for item in items_result.data:
                            op_id = item['orden_produccion_id']
                            if op_id not in pedidos_por_op:
                                pedidos_por_op[op_id] = []
                            pedido_info = item.get('pedido')
                            if pedido_info and not any(p['id'] == pedido_info['id'] for p in pedidos_por_op.get(op_id, [])):
                                pedidos_por_op[op_id].append(pedido_info)

                # 2. Identificar OPs hijas que necesitan heredar la asociación
                parent_op_ids_needed = set()
                for op in processed_data:
                    parent_id = op.get('id_op_padre')
                    if parent_id and not pedidos_por_op.get(op['id']):
                        parent_op_ids_needed.add(parent_id)

                # 3. Obtener los pedidos de los padres, si es necesario
                pedidos_de_padres = {}
                if parent_op_ids_needed:
                    parent_items_result = self.db.table('pedido_items').select(
                        'orden_produccion_id, pedido:pedidos!pedido_items_pedido_id_fkey(id, nombre_cliente, estado)'
                    ).in_('orden_produccion_id', list(parent_op_ids_needed)).execute()

                    if parent_items_result.data:
                        for item in parent_items_result.data:
                            parent_op_id = item['orden_produccion_id']
                            if parent_op_id not in pedidos_de_padres:
                                pedidos_de_padres[parent_op_id] = []
                            pedido_info = item.get('pedido')
                            if pedido_info and not any(p['id'] == pedido_info['id'] for p in pedidos_de_padres.get(parent_op_id, [])):
                                pedidos_de_padres[parent_op_id].append(pedido_info)

                # 4. Asignar los pedidos a cada OP (directos o heredados)
                for op in processed_data:
                    op_id = op['id']
                    parent_id = op.get('id_op_padre')
                    
                    direct_pedidos = pedidos_por_op.get(op_id)
                    if direct_pedidos:
                        op['pedidos_asociados'] = direct_pedidos
                    elif parent_id and parent_id in pedidos_de_padres:
                        op['pedidos_asociados'] = pedidos_de_padres[parent_id]
                    else:
                        op['pedidos_asociados'] = []
                
                # --- FIN DE LA LÓGICA DE HERENCIA ---

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
                
                # --- OBTENER ORDENES DE COMPRA ASOCIADAS ---
                ocs_res = self.db.table('ordenes_compra').select('id, codigo_oc, estado').eq('orden_produccion_id', orden_id).execute()
                item['ocs_asociadas'] = ocs_res.data if ocs_res.data else []

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

    def get_all_in_date_range(self, fecha_inicio: datetime, fecha_fin: datetime) -> Dict:
        """
        Obtiene todas las órdenes de producción dentro de un rango de fechas.
        """
        try:
            query = self.db.table(self.get_table_name()).select("*")
            query = query.gte('fecha_inicio', fecha_inicio.isoformat())
            query = query.lte('fecha_inicio', fecha_fin.isoformat())
            result = query.execute()

            if result.data:
                return {'success': True, 'data': result.data}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error al obtener órdenes de producción por rango de fecha: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_volumen_produccion_por_fecha(self, fecha_inicio: datetime, fecha_fin: datetime) -> Dict:
        """
        Calcula el volumen de producción total por día dentro de un rango de fechas.
        """
        try:
            # Selecciona la fecha de finalización y suma las cantidades producidas
            result = self.db.table(self.get_table_name()).select(
                "fecha_fin, cantidad_producida"
            ).gte(
                'fecha_fin', fecha_inicio.isoformat()
            ).lte(
                'fecha_fin', fecha_fin.isoformat()
            ).eq(
                'estado', 'COMPLETADA'
            ).execute()

            if result.data:
                # Agrupa los resultados por día en Python
                volumen_por_dia = {}
                for record in result.data:
                    # Extrae solo la parte de la fecha del string ISO
                    dia = record['fecha_fin'].split('T')[0]
                    if dia not in volumen_por_dia:
                        volumen_por_dia[dia] = 0
                    volumen_por_dia[dia] += record['cantidad_producida']

                # Convierte el diccionario a una lista de diccionarios para un manejo más fácil
                datos_procesados = [{"fecha": dia, "volumen": volumen} for dia, volumen in sorted(volumen_por_dia.items())]
                return {'success': True, 'data': datos_procesados}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error al obtener el volumen de producción por fecha: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_comparativa_plan_vs_real(self, fecha_inicio: datetime, fecha_fin: datetime, limite: int = 10) -> Dict:
        """
        Obtiene las últimas N órdenes de producción completadas para comparar
        la cantidad planificada versus la cantidad real producida.
        """
        try:
            # Obtiene las órdenes ordenadas por fecha de finalización descendente
            result = self.db.table(self.get_table_name()).select(
                "id, cantidad_planificada, cantidad_producida, producto_id, productos(nombre)"
            ).gte(
                'fecha_fin', fecha_inicio.isoformat()
            ).lte(
                'fecha_fin', fecha_fin.isoformat()
            ).eq(
                'estado', 'COMPLETADA'
            ).order(
                'fecha_fin', desc=True
            ).limit(limite).execute()

            if result.data:
                # Da la vuelta a los datos para que en el gráfico se muestren del más antiguo al más nuevo
                datos_invertidos = result.data[::-1]
                return {'success': True, 'data': datos_invertidos}
            else:
                return {'success': True, 'data': []}

        except Exception as e:
            logger.error(f"Error al obtener la comparativa plan vs. real: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}