from .base_model import BaseModel

class AlertaRiesgoModel(BaseModel):
    def __init__(self, id=None, codigo=None, origen_tipo_entidad=None, origen_id_entidad=None, estado=None, motivo=None, comentarios=None, url_evidencia=None, fecha_creacion=None, resolucion_seleccionada=None):
       
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
        Toma una lista de {'tipo_entidad': T, 'id_entidad': ID} y devuelve los detalles.
        """
        ids_por_tipo = {}
        for afectado in afectados:
            tipo = afectado['tipo_entidad']
            if tipo not in ids_por_tipo:
                ids_por_tipo[tipo] = []
            ids_por_tipo[tipo].append(afectado['id_entidad'])

        detalles = {}
        if 'pedido' in ids_por_tipo:
            pedidos_res = self.db.table('pedidos').select(
                'id,nombre_cliente, fecha_requerido, estado'
            ).in_('id', ids_por_tipo['pedido']).execute().data
            detalles['pedidos'] = pedidos_res

        if 'lote_producto' in ids_por_tipo:
            lotes_res = self.db.table('lotes_productos').select(
                'id_lote, numero_lote, fecha_produccion'
            ).in_('id_lote', ids_por_tipo['lote_producto']).execute().data
            detalles['lotes_producto'] = lotes_res
        
        if 'orden_produccion' in ids_por_tipo:
            ops_res = self.db.table('ordenes_produccion').select(
                'id, codigo, fecha_inicio'
            ).in_('id', ids_por_tipo['orden_produccion']).execute().data
            detalles['ordenes_produccion'] = ops_res

        if 'lote_insumo' in ids_por_tipo:
            insumos_res = self.db.table('insumos_inventario').select(
                'id_lote, codigo_lote, insumos_catalogo:id_insumo(nombre)'
            ).in_('id_lote', ids_por_tipo['lote_insumo']).execute().data
            detalles['lotes_insumo'] = insumos_res

        return detalles

    def asociar_afectados(self, alerta_id, afectados):
        if not afectados:
            return None # No hacer nada si no hay afectados
        records = [{'alerta_id': alerta_id, 'tipo_entidad': a['tipo_entidad'], 'id_entidad': str(a['id_entidad'])} for a in afectados]
        return self.db.table('alerta_riesgo_afectados').insert(records).execute()
    
    def actualizar_estado_afectados(self, alerta_id, pedidos_ids, resolucion, documento_id=None):
        update_data = {
            'estado': 'resuelto',
            'resolucion_aplicada': resolucion,
        }
        if documento_id:
            update_data['id_documento_relacionado'] = documento_id

        query = self.db.table('alerta_riesgo_afectados').update(update_data).eq('alerta_id', alerta_id)
        
        # PostgREST no soporta `in` con múltiples valores en un `update` directamente sobre una lista.
        # Se debe iterar o usar una función RPC. Iterar es más simple aquí.
        for pedido_id in pedidos_ids:
            self.db.table('alerta_riesgo_afectados').update(update_data).eq('alerta_id', alerta_id).eq('id_entidad', pedido_id).eq('tipo_entidad', 'pedido').execute()
        
        return self.verificar_y_cerrar_alerta(alerta_id)

    def verificar_y_cerrar_alerta(self, alerta_id):
        res = self.db.table('alerta_riesgo_afectados').select('id', count='exact').eq('alerta_id', alerta_id).eq('estado', 'pendiente').execute()
        
        if res.count == 0:
            # No quedan pendientes, cerrar la alerta
            self.update(alerta_id, {'estado': 'Resuelta'})
            return True # Indica que la alerta se cerró
        return False # Indica que la alerta sigue abierta

    def obtener_afectados_con_estado(self, alerta_id):
        return self.db.table('alerta_riesgo_afectados').select(
            '*'
        ).eq('alerta_id', alerta_id).execute().data


    def get_trazabilidad_afectados(self, tipo_entidad, id_entidad):
        """
        Realiza en Python las consultas necesarias para resolver la trazabilidad
        y devolver la lista de entidades afectadas por la entidad origen.

        Retorna una lista de diccionarios: { 'tipo_entidad': <str>, 'id_entidad': <str> }
        """
        try:
            afectados = []
            # Normalizar id como string
            pid = str(id_entidad)

            if tipo_entidad == 'lote_insumo':
                # 1) Ordenes de produccion que utilizaron el lote
                res_ops = self.db.table('reservas_insumos').select('orden_produccion_id').eq('lote_inventario_id', pid).execute().data or []
                op_ids = list({str(r.get('orden_produccion_id')) for r in res_ops if r.get('orden_produccion_id') is not None})
                for oid in op_ids:
                    afectados.append({'tipo_entidad': 'orden_produccion', 'id_entidad': oid})

                # 2) Lotes de producto generados por esas OPs
                if op_ids:
                    res_lps = self.db.table('lotes_productos').select('id_lote').in_('orden_produccion_id', op_ids).execute().data or []
                    lp_ids = list({str(r.get('id_lote')) for r in res_lps if r.get('id_lote') is not None})
                    for lid in lp_ids:
                        afectados.append({'tipo_entidad': 'lote_producto', 'id_entidad': lid})

                    # 3) Pedidos que contienen esos lotes de producto
                    if lp_ids:
                        res_ped = self.db.table('reservas_productos').select('pedido_id').in_('lote_producto_id', lp_ids).execute().data or []
                        ped_ids = list({str(r.get('pedido_id')) for r in res_ped if r.get('pedido_id') is not None})
                        for pidv in ped_ids:
                            afectados.append({'tipo_entidad': 'pedido', 'id_entidad': pidv})

            elif tipo_entidad == 'lote_producto':
                # Pedidos que incluyen el lote de producto
                res_ped = self.db.table('reservas_productos').select('pedido_id').eq('lote_producto_id', pid).execute().data or []
                ped_ids = list({str(r.get('pedido_id')) for r in res_ped if r.get('pedido_id') is not None})
                for pidv in ped_ids:
                    afectados.append({'tipo_entidad': 'pedido', 'id_entidad': pidv})

                # OP que generó el lote
                res_lp = self.db.table('lotes_productos').select('orden_produccion_id').eq('id_lote', pid).single().execute()
                if getattr(res_lp, 'data', None):
                    op_id = res_lp.data.get('orden_produccion_id')
                    if op_id is not None:
                        afectados.append({'tipo_entidad': 'orden_produccion', 'id_entidad': str(op_id)})

            elif tipo_entidad == 'orden_produccion':
                # Lotes producto de la OP
                res_lps = self.db.table('lotes_productos').select('id_lote').eq('orden_produccion_id', pid).execute().data or []
                lp_ids = list({str(r.get('id_lote')) for r in res_lps if r.get('id_lote') is not None})
                for lid in lp_ids:
                    afectados.append({'tipo_entidad': 'lote_producto', 'id_entidad': lid})

                # Pedidos relacionados a esos lotes
                if lp_ids:
                    res_ped = self.db.table('reservas_productos').select('pedido_id').in_('lote_producto_id', lp_ids).execute().data or []
                    ped_ids = list({str(r.get('pedido_id')) for r in res_ped if r.get('pedido_id') is not None})
                    for pidv in ped_ids:
                        afectados.append({'tipo_entidad': 'pedido', 'id_entidad': pidv})

            elif tipo_entidad == 'pedido':
                # Para pedidos, devolver los lotes de producto incluidos
                res_lps = self.db.table('reservas_productos').select('lote_producto_id').eq('pedido_id', pid).execute().data or []
                lp_ids = list({str(r.get('lote_producto_id')) for r in res_lps if r.get('lote_producto_id') is not None})
                for lid in lp_ids:
                    afectados.append({'tipo_entidad': 'lote_producto', 'id_entidad': lid})

            # Eliminar duplicados manteniendo orden de aparición
            seen = set()
            unique = []
            for a in afectados:
                key = (a['tipo_entidad'], a['id_entidad'])
                if key not in seen:
                    seen.add(key)
                    unique.append(a)

            return unique

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error resolviendo trazabilidad en Python: {e}", exc_info=True)
            return []
