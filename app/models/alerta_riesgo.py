from .base_model import BaseModel

class AlertaRiesgoModel(BaseModel):
    def __init__(self, id=None, codigo=None, origen_tipo_entidad=None, origen_id_entidad=None, estado=None, motivo=None, comentarios=None, url_evidencia=None, fecha_creacion=None, resolucion_seleccionada=None, id_usuario_creador=None):
       
        super().__init__()
        self.id = id
        self.codigo = codigo
        self.origen_tipo_entidad = origen_tipo_entidad
        self.origen_id_entidad = origen_id_entidad
        self.estado = estado
        self.motivo = motivo
        self.comentarios = comentarios
        self.url_evidencia = url_evidencia
        self.fecha_creacion = fecha_creacion
        self.resolucion_seleccionada = resolucion_seleccionada
        self.id_usuario_creador = id_usuario_creador

    @classmethod
    def get_table_name(cls):
        return "alerta_riesgo"

    @classmethod
    def get_id_column(cls):
        return "id"
    
    def obtener_por_codigo(self, codigo_alerta):
        try:
            resultado =self.db.table(self.get_table_name()).select('*').eq('codigo', codigo_alerta).execute()
            if( resultado.data):
                return {'success': True, 'data': resultado.data}
            else:
                return {'success': False, 'error': 'Alerta no encontrada'}
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error obteniendo alerta por código {codigo_alerta}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
        
    def obtener_afectados(self, alerta_id):
        return self.db.table('alerta_riesgo_afectados').select(
        'tipo_entidad, id_entidad'
        ).eq('alerta_id', alerta_id).execute().data

    def obtener_afectados_detalle(self, alerta_id):
        afectados_res = self.obtener_afectados(alerta_id)
        if not afectados_res:
            return {}
        return self.obtener_afectados_detalle_para_previsualizacion(afectados_res)

    def obtener_afectados_detalle_para_previsualizacion(self, afectados):
        """
        Toma una lista de {'tipo_entidad': T, 'id_entidad': ID} y devuelve los detalles,
        manejando correctamente IDs de tipo int y UUID (string).
        """
        ids_por_tipo = {}
        for afectado in afectados:
            tipo = afectado['tipo_entidad']
            if tipo not in ids_por_tipo:
                ids_por_tipo[tipo] = []
            ids_por_tipo[tipo].append(afectado['id_entidad'])

        detalles = {}
        
        # Entidades con IDs numéricos
        for tipo_entidad in ['pedido', 'lote_producto', 'orden_produccion']:
            if tipo_entidad in ids_por_tipo:
                try:
                    # Filtrar solo los IDs que son numéricos
                    ids_numericos = [int(id_val) for id_val in ids_por_tipo[tipo_entidad] if isinstance(id_val, int) or (isinstance(id_val, str) and id_val.isdigit())]
                    if not ids_numericos: continue

                    if tipo_entidad == 'pedido':
                        res = self.db.table('pedidos').select('id, nombre_cliente, fecha_requerido, estado').in_('id', ids_numericos).execute().data
                        detalles['pedidos'] = res
                    elif tipo_entidad == 'lote_producto':
                        res = self.db.table('lotes_productos').select('id_lote, numero_lote, fecha_produccion').in_('id_lote', ids_numericos).execute().data
                        detalles['lotes_producto'] = res
                    elif tipo_entidad == 'orden_produccion':
                        res = self.db.table('ordenes_produccion').select('id, codigo, fecha_inicio').in_('id', ids_numericos).execute().data
                        detalles['ordenes_produccion'] = res
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error al buscar detalles para {tipo_entidad} con IDs numéricos: {e}", exc_info=True)

        # Entidades con IDs UUID (string)
        if 'lote_insumo' in ids_por_tipo:
            try:
                # Filtrar solo los IDs que son strings (potencialmente UUIDs)
                ids_uuid = [str(id_val) for id_val in ids_por_tipo['lote_insumo'] if isinstance(id_val, str)]
                if not ids_uuid: return detalles

                res = self.db.table('insumos_inventario').select(
                    'id_lote, numero_lote_proveedor, insumos_catalogo:id_insumo(nombre)'
                ).in_('id_lote', ids_uuid).execute().data
                detalles['lotes_insumo'] = res
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error al buscar detalles para lote_insumo con IDs UUID: {e}", exc_info=True)

        return detalles

    def asociar_afectados(self, alerta_id, afectados, estados_previos):
        if not afectados:
            return None # No hacer nada si no hay afectados
        records = []
        for a in afectados:
            entidad_key = (a['tipo_entidad'], str(a['id_entidad']))
            estado_previo = estados_previos.get(entidad_key, 'Desconocido')
            records.append({
                'alerta_id': alerta_id,
                'tipo_entidad': a['tipo_entidad'],
                'id_entidad': str(a['id_entidad']),
                'estado': 'pendiente',
                'estado_previo': estado_previo
            })
        return self.db.table('alerta_riesgo_afectados').insert(records).execute()
    
    def actualizar_estado_afectados(self, alerta_id, entidad_ids, resolucion, tipo_entidad, id_usuario_resolucion, documento_id=None):
        update_data = {
            'estado': 'resuelto',
            'resolucion_aplicada': resolucion,
            'id_usuario_resolucion': id_usuario_resolucion
        }
        if documento_id:
            update_data['id_documento_relacionado'] = documento_id

        # Convertir todos los IDs a string para consistencia en la consulta
        entidad_ids_str = [str(eid) for eid in entidad_ids]

        self.db.table('alerta_riesgo_afectados').update(update_data)\
            .eq('alerta_id', alerta_id)\
            .eq('tipo_entidad', tipo_entidad)\
            .in_('id_entidad', entidad_ids_str)\
            .execute()

        return self.verificar_y_cerrar_alerta(alerta_id)

    def verificar_y_cerrar_alerta(self, alerta_id):
        res = self.db.table('alerta_riesgo_afectados').select('id', count='exact').eq('alerta_id', alerta_id).eq('estado', 'pendiente').execute()
        
        if res.count == 0:
            # No quedan pendientes, cerrar la alerta
            self.update(alerta_id, {'estado': 'Resuelta'})
            
            # Ahora, verificar y actualizar el estado `en_alerta` de las entidades afectadas
            afectados = self.obtener_afectados(alerta_id)
            for afectado in afectados:
                sigue_en_alerta = self.entidad_esta_en_otras_alertas_activas(
                    afectado['tipo_entidad'], 
                    afectado['id_entidad'],
                    alerta_id # Excluimos la alerta actual que acabamos de cerrar
                )
                
                if not sigue_en_alerta:
                    self._actualizar_flag_en_alerta_entidad(afectado['tipo_entidad'], afectado['id_entidad'], False)

            return True # Indica que la alerta se cerró
        return False # Indica que la alerta sigue abierta

    def resolver_orden_produccion_si_corresponde(self, op_id: int, alerta_id: int, usuario_id: int):
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 1. Obtener todos los lotes de insumo asociados a la OP
            reservas_res = self.db.table('reserva_insumos').select('lote_inventario_id').eq('orden_produccion_id', op_id).execute().data
            if not reservas_res:
                logger.info(f"OP {op_id} no tiene insumos reservados. Marcando como resuelta en alerta {alerta_id}.")
                self.actualizar_estado_afectados(alerta_id, [op_id], 'sin_insumos_comprometidos', 'orden_produccion', usuario_id)
                return

            lote_insumo_ids = [r['lote_inventario_id'] for r in reservas_res]

            # 2. Verificar si alguno de esos lotes sigue en cuarentena DENTRO DE ESTA ALERTA
            cuarentena_res = self.db.table('alerta_riesgo_afectados')\
                .select('id', count='exact')\
                .eq('alerta_id', alerta_id)\
                .eq('tipo_entidad', 'lote_insumo')\
                .in_('id_entidad', lote_insumo_ids)\
                .eq('estado', 'pendiente')\
                .execute()

            # 3. Si no hay lotes pendientes en esta alerta, resolver la OP para esta alerta
            if cuarentena_res.count == 0:
                logger.info(f"Todos los insumos para la OP {op_id} han sido liberados en el contexto de la alerta {alerta_id}. Marcando OP como resuelta.")
                self.actualizar_estado_afectados(alerta_id, [op_id], 'insumos_liberados', 'orden_produccion', usuario_id)

        except Exception as e:
            logger.error(f"Error en resolver_orden_produccion_si_corresponde para OP {op_id}, Alerta {alerta_id}: {e}", exc_info=True)


    def _actualizar_flag_en_alerta_entidad(self, tipo_entidad, id_entidad, en_alerta):
        """
        Actualiza el flag 'en_alerta' para una entidad específica.
        """
        TABLA_MAP = {
            'lote_insumo': ('insumos_inventario', 'id_lote'),
            'orden_produccion': ('ordenes_produccion', 'id'),
            'lote_producto': ('lotes_productos', 'id_lote'),
            'pedido': ('pedidos', 'id')
        }
        
        if tipo_entidad not in TABLA_MAP:
            return

        tabla, id_columna = TABLA_MAP[tipo_entidad]
        
        try:
            self.db.table(tabla).update({'en_alerta': en_alerta}).eq(id_columna, str(id_entidad)).execute()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error actualizando flag 'en_alerta' para {tipo_entidad}:{id_entidad} en tabla {tabla}: {e}", exc_info=True)


    def entidad_esta_en_otras_alertas_activas(self, tipo_entidad, id_entidad, alerta_id_a_excluir):
        """
        Verifica si una entidad específica está afectada por CUALQUIER OTRA alerta de riesgo
        que todavía esté en estado 'Pendiente'. Excluye la alerta que se está cerrando.
        """
        try:
            # 1. Encontrar todos los `alerta_id` donde la entidad está afectada
            afectaciones = self.db.table('alerta_riesgo_afectados').select('alerta_id').eq('tipo_entidad', tipo_entidad).eq('id_entidad', str(id_entidad)).execute().data
            if not afectaciones:
                return False

            # 2. Extraer los IDs de alerta, excluyendo la actual
            ids_de_alerta = [a['alerta_id'] for a in afectaciones if a['alerta_id'] != alerta_id_a_excluir]
            if not ids_de_alerta:
                return False

            # 3. Verificar si alguna de esas alertas está 'Pendiente'
            resultado = self.db.table('alerta_riesgo').select('id', count='exact').in_('id', ids_de_alerta).eq('estado', 'Pendiente').execute()

            return resultado.count > 0

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error verificando si la entidad {tipo_entidad}:{id_entidad} está en otras alertas: {e}", exc_info=True)
            return True # Ser precavido: si hay un error, asumir que sí está en alerta para no quitar el flag por error.

    def actualizar_estado_afectados_por_entidad(self, tipo_entidad: str, id_entidad, resolucion: str, usuario_id: int):
        """
        Actualiza el estado de una entidad específica en TODAS las alertas en las que aparece.
        """
        try:
            update_data = {
                'estado': 'resuelto',
                'resolucion_aplicada': resolucion,
                'id_usuario_resolucion': usuario_id
            }
            self.db.table('alerta_riesgo_afectados').update(update_data).eq('tipo_entidad', tipo_entidad).eq('id_entidad', str(id_entidad)).execute()
            
            # Después de actualizar, verificar si alguna de las alertas afectadas puede cerrarse.
            self.verificar_y_cerrar_alerta_por_entidad_resuelta(tipo_entidad, id_entidad)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en actualizar_estado_afectados_por_entidad para {tipo_entidad}:{id_entidad}: {e}", exc_info=True)


    def obtener_afectados_con_estado(self, alerta_id):
        return self.db.table('alerta_riesgo_afectados').select(
            '*'
        ).eq('alerta_id', alerta_id).execute().data

    def verificar_y_cerrar_alerta_por_entidad_resuelta(self, tipo_entidad, id_entidad):
        """
        Cuando una entidad (ej. un lote) se resuelve (sale de cuarentena), esta
        función busca todas las alertas en las que estaba involucrada y verifica
        si alguna de ellas puede cerrarse.
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 1. Encontrar todas las filas de 'afectados' para esta entidad
            afectaciones = self.db.table('alerta_riesgo_afectados') \
                .select('alerta_id') \
                .eq('tipo_entidad', tipo_entidad) \
                .eq('id_entidad', str(id_entidad)) \
                .execute().data
            
            if not afectaciones:
                logger.info(f"La entidad {tipo_entidad}:{id_entidad} no está afectada por ninguna alerta. No se hace nada.")
                return

            # 2. Iterar sobre cada alerta encontrada y verificar si se puede cerrar
            alerta_ids = {a['alerta_id'] for a in afectaciones} # Usar un set para evitar duplicados
            logger.info(f"La entidad {tipo_entidad}:{id_entidad} está en {len(alerta_ids)} alerta(s). Verificando si alguna puede cerrarse...")
            
            for alerta_id in alerta_ids:
                self.verificar_y_cerrar_alerta(alerta_id)

        except Exception as e:
            logger.error(f"Error en verificar_y_cerrar_alerta_por_entidad_resuelta para {tipo_entidad}:{id_entidad}: {e}", exc_info=True)

    def registrar_resolucion_afectado(self, alerta_id, tipo_entidad, id_entidad, estado_resolucion, resolucion_aplicada, usuario_id, id_documento_relacionado=None):
        """
        Registra la resolución para una única entidad afectada en una alerta.
        """
        try:
            update_data = {
                'estado': estado_resolucion,
                'resolucion_aplicada': resolucion_aplicada,
                'id_usuario_resolucion': usuario_id
            }
            if id_documento_relacionado:
                update_data['id_documento_relacionado'] = id_documento_relacionado
            
            result = self.db.table('alerta_riesgo_afectados').update(update_data)\
                .eq('alerta_id', alerta_id)\
                .eq('tipo_entidad', tipo_entidad)\
                .eq('id_entidad', str(id_entidad))\
                .execute()
            
            return {'success': True, 'data': result.data}
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al registrar resolución para {tipo_entidad}:{id_entidad} en alerta {alerta_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_all_paginated(self, page: int, per_page: int, filters: dict, select_query: str = None) -> dict:
        """
        Obtiene una lista paginada de alertas de riesgo, incluyendo datos agregados como conclusión, participantes y pendientes.
        """
        try:
            offset = (page - 1) * per_page
            
            # Seleccionamos los campos necesarios, incluyendo conclusion_final
            query = self._get_query_builder().select(
                '*, creador:usuarios!alerta_riesgo_id_usuario_creador_fkey(nombre, apellido)', 
                count='exact'
            )

            if filters:
                for key, value in filters.items():
                    if value:
                        query = query.ilike(key, f'%{value}%')
            
            query = query.order('id', desc=True).range(offset, offset + per_page - 1)
            
            result = query.execute()
            
            alertas = result.data if result.data else []
            
            # Enriquecer con datos agregados (N+1 optimizado no es posible fácilmente con postgrest sin funciones RPC complejas, 
            # pero haremos queries agrupadas si es posible o iterativas dado que la paginación limita el impacto)
            
            if alertas:
                alerta_ids = [a['id'] for a in alertas]
                
                # 1. Contar pendientes
                pendientes_res = self.db.table('alerta_riesgo_afectados').select('alerta_id').in_('alerta_id', alerta_ids).eq('estado', 'pendiente').execute()
                pendientes_map = {}
                if pendientes_res.data:
                    for p in pendientes_res.data:
                        pendientes_map[p['alerta_id']] = pendientes_map.get(p['alerta_id'], 0) + 1
                
                # 2. Obtener participantes (resolutores únicos)
                resolutores_res = self.db.table('alerta_riesgo_afectados').select('alerta_id, usuarios!alerta_riesgo_afectados_id_usuario_resolucion_fkey(nombre, apellido)').in_('alerta_id', alerta_ids).not_.is_('id_usuario_resolucion', 'null').execute()
                participantes_map = {}
                if resolutores_res.data:
                    for r in resolutores_res.data:
                        aid = r['alerta_id']
                        user_data = r.get('usuarios')
                        if user_data:
                            nombre_completo = f"{user_data.get('nombre', '')} {user_data.get('apellido', '')}".strip()
                            if aid not in participantes_map: participantes_map[aid] = set()
                            participantes_map[aid].add(nombre_completo)

                # Asignar datos a las alertas
                for alerta in alertas:
                    alerta['pendientes_count'] = pendientes_map.get(alerta['id'], 0)
                    alerta['participantes_nombres'] = list(participantes_map.get(alerta['id'], []))
                    
                    if alerta.get('creador'):
                        nombre_creador = f"{alerta['creador'].get('nombre', '')} {alerta['creador'].get('apellido', '')}".strip()
                        alerta['nombre_creador'] = nombre_creador

            return {
                'success': True,
                'data': alertas,
                'count': result.count
            }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al obtener alertas paginadas: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}
