from .base_model import BaseModel

class AlertaRiesgoModel(BaseModel):
    def __init__(self, id=None, codigo=None, origen_tipo_entidad=None, origen_id_entidad=None, estado=None, motivos=None, detalle_motivo=None, fecha_creacion=None, resolucion_seleccionada=None):
        # Inicializar BaseModel para que self.db y self.table_name estén disponibles
        super().__init__()
        self.id = id
        self.codigo = codigo
        self.origen_tipo_entidad = origen_tipo_entidad
        self.origen_id_entidad = origen_id_entidad
        self.estado = estado
        self.motivos = motivos
        self.detalle_motivo = detalle_motivo
        self.fecha_creacion = fecha_creacion
        self.resolucion_seleccionada = resolucion_seleccionada

    @classmethod
    def get_table_name(cls):
        return "alerta_riesgo"

    @classmethod
    def get_id_column(cls):
        return "id"

    def obtener_afectados(self, alerta_id):
        return self.db.table('alerta_riesgo_afectados').select(
            '*, pedidos:id_entidad(id, nombre_cliente, fecha_solicitud, estado, clientes:id_cliente(nombre))'
        ).eq('alerta_id', alerta_id).eq('tipo_entidad', 'pedido').execute().data

    def asociar_afectados(self, alerta_id, afectados):
        records = [{'alerta_id': alerta_id, 'tipo_entidad': a['tipo_entidad'], 'id_entidad': str(a['id_entidad'])} for a in afectados]
        return self.db.table('alerta_riesgo_afectados').insert(records).execute()

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
