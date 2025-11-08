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
                'id_lote, numero_lote_proveedor, insumos_catalogo:id_insumo(nombre)'
            ).in_('id_lote', ids_por_tipo['lote_insumo']).execute().data
            detalles['lotes_insumo'] = insumos_res

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
            return True # Indica que la alerta se cerró
        return False # Indica que la alerta sigue abierta

    def obtener_afectados_con_estado(self, alerta_id):
        return self.db.table('alerta_riesgo_afectados').select(
            '*'
        ).eq('alerta_id', alerta_id).execute().data
