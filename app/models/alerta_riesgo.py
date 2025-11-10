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

    def asociar_afectados(self, alerta_id, afectados):
        if not afectados:
            return None # No hacer nada si no hay afectados
        records = [{
            'alerta_id': alerta_id, 
            'tipo_entidad': a['tipo_entidad'], 
            'id_entidad': str(a['id_entidad']),
            'estado': 'pendiente'  # Añadir estado inicial por defecto
        } for a in afectados]
        return self.db.table('alerta_riesgo_afectados').insert(records).execute()
    
    def actualizar_estado_afectados(self, alerta_id, entidad_ids, resolucion, tipo_entidad, id_usuario_resolucion, documento_id=None):
        update_data = {
            'estado': 'resuelto',
            'resolucion_aplicada': resolucion,
            'id_usuario_resolucion': id_usuario_resolucion
        }
        if documento_id:
            update_data['id_documento_relacionado'] = documento_id

        query = self.db.table('alerta_riesgo_afectados').update(update_data).eq('alerta_id', alerta_id)
        
        # PostgREST no soporta `in` con múltiples valores en un `update` directamente sobre una lista.
        # Se debe iterar o usar una función RPC. Iterar es más simple aquí.
        for entidad_id in entidad_ids:
            self.db.table('alerta_riesgo_afectados').update(update_data).eq('alerta_id', alerta_id).eq('id_entidad', entidad_id).eq('tipo_entidad', tipo_entidad).execute()
          
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


    def obtener_afectados_con_estado(self, alerta_id):
        return self.db.table('alerta_riesgo_afectados').select(
            '*'
        ).eq('alerta_id', alerta_id).execute().data
