from .base_model import BaseModel
from postgrest import APIError

class TrazabilidadModel(BaseModel):
    """
    Modelo para encapsular las consultas complejas de trazabilidad.
    """
    def __init__(self):
        super().__init__()

    def obtener_entidades_afectadas(self, tipo_entidad, id_entidad):
        """
        Reemplazo en Python para el stored procedure 'get_trazabilidad_afectados'.
        Dada una entidad de origen, encuentra todos los pedidos y lotes de producto afectados.
        """
        lotes_producto_afectados_ids = set()
        pedidos_afectados_ids = set()

        if tipo_entidad == 'lote_insumo':
            # 1. Encontrar OPs que usaron el lote de insumo
            reservas_insumo = self.db.table('reservas_insumos').select('orden_produccion_id').eq('lote_inventario_id', id_entidad).execute().data
            op_ids = {r['orden_produccion_id'] for r in reservas_insumo}

            # 2. Encontrar Lotes de Producto generados por esas OPs
            if op_ids:
                lotes_producto = self.db.table('lotes_productos').select('id_lote').in_('orden_produccion_id', list(op_ids)).execute().data
                lotes_producto_afectados_ids.update([lp['id_lote'] for lp in lotes_producto])

        elif tipo_entidad == 'orden_produccion':
            # 1. Encontrar Lotes de Producto generados por esa OP
            lotes_producto = self.db.table('lotes_productos').select('id_lote').eq('orden_produccion_id', id_entidad).execute().data
            lotes_producto_afectados_ids.update([lp['id_lote'] for lp in lotes_producto])
        
        elif tipo_entidad == 'lote_producto':
            lotes_producto_afectados_ids.add(id_entidad)

        # 3. Para todos los lotes de producto afectados, encontrar los pedidos asociados
        if lotes_producto_afectados_ids:
            reservas_producto = self.db.table('reservas_productos').select('pedido_id').in_('lote_producto_id', list(lotes_producto_afectados_ids)).execute().data
            pedidos_afectados_ids.update([rp['pedido_id'] for rp in reservas_producto])

        # 4. Formatear la salida como lo esperaba el controlador
        return [
            {'tipo': 'lote_producto', 'id': str(lp_id)} for lp_id in lotes_producto_afectados_ids
        ] + [
            {'tipo': 'pedido', 'id': str(p_id)} for p_id in pedidos_afectados_ids
        ]

    def _obtener_riesgo_proveedor(self, proveedor_id):
        if not proveedor_id:
            return {"total_lotes": 0, "lotes_rechazados": 0, "tasa_fallos": "0.00"}
        try:
            total_lotes_res = self.db.table('insumos_inventario').select('id_lote', count='exact').eq('id_proveedor', proveedor_id).execute()
            total_lotes = total_lotes_res.count or 0
            if total_lotes == 0:
                return {"total_lotes": 0, "lotes_rechazados": 0, "tasa_fallos": "0.00"}
            rechazados_res = self.db.table('insumos_inventario').select(
                'id_lote', count='exact'
            ).eq('id_proveedor', proveedor_id).eq('estado_calidad', 'Rechazado').execute()
            lotes_rechazados = rechazados_res.count or 0
            tasa_fallos = (lotes_rechazados / total_lotes) * 100 if total_lotes > 0 else 0
            return {
                "total_lotes": total_lotes,
                "lotes_rechazados": lotes_rechazados,
                "tasa_fallos": f"{tasa_fallos:.2f}"
            }
        except APIError as e:
            print(f"Error al calcular riesgo de proveedor: {e}")
            return {"total_lotes": 0, "lotes_rechazados": 0, "tasa_fallos": "0.00"}

    def obtener_trazabilidad_completa_lote_insumo(self, lote_id):
        lote_insumo_res = self.db.table('insumos_inventario').select(
            '*, insumos_catalogo:id_insumo(nombre, unidad_medida), proveedores:id_proveedor(id, nombre)'
        ).eq('id_lote', lote_id).single().execute()
        lote_insumo = lote_insumo_res.data
        if not lote_insumo: return None

        orden_compra = None
        codigo_oc = lote_insumo.get('documento_ingreso')
        if codigo_oc:
            oc_res = self.db.table('ordenes_compra').select('id, codigo_oc').eq('codigo_oc', codigo_oc).single().execute()
            orden_compra = oc_res.data

        reservas = self.db.table('reservas_insumos').select(
            # evitar columnas inexistentes: usar numero_lote y cantidad_inicial en lotes_productos
            'cantidad_reservada, ordenes_produccion!inner(id, codigo, lotes_productos!orden_produccion_id(id_lote, numero_lote, cantidad_inicial))'
        ).eq('lote_inventario_id', lote_id).execute().data
        
        proveedor_id = lote_insumo.get('id_proveedor')
        riesgo_proveedor = self._obtener_riesgo_proveedor(proveedor_id)
        
        resumen_origen = {
            "insumo": lote_insumo.get('insumos_catalogo', {}).get('nombre', 'N/A'),
            "proveedor": lote_insumo.get('proveedores', {}).get('nombre', 'N/A'),
            "lote_proveedor": lote_insumo.get('lote_proveedor', 'N/A'),
            "orden_compra": {"id": orden_compra.get('id'), "codigo": orden_compra.get('codigo_oc')} if orden_compra else None,
            "recepcion": lote_insumo.get('fecha_ingreso', 'N/A'),
            "calidad": lote_insumo.get('estado_calidad', 'Pendiente')
        }

        ops_usadas = []
        productos_generados = []
        if reservas:
            for reserva in reservas:
                op = reserva.get('ordenes_produccion')
                if op:
                    ops_usadas.append({"id": op.get('id'), "codigo": op.get('codigo'), "cantidad": reserva.get('cantidad_reservada')})
                    for lp in op.get('lotes_productos', []):
                        # lotes_productos expone 'id_lote' y 'numero_lote' según el esquema
                        productos_generados.append({"id": lp.get('id_lote'), "codigo": lp.get('numero_lote')})
        
        resumen_uso = {"ops": ops_usadas, "productos": list({p['id']: p for p in productos_generados}.values())}
        
        nodes, edges = [], []
        li_id_node = f"li_{lote_insumo['id_lote']}"
        nodes.append({"id": li_id_node, "label": f"LI: {resumen_origen['insumo']}", "group": "lote_insumo", "url": f"/inventario/lote/{lote_insumo['id_lote']}"})

        if resumen_origen['orden_compra'] and resumen_origen['orden_compra']['id']:
            oc_id, oc_codigo = resumen_origen['orden_compra']['id'], resumen_origen['orden_compra']['codigo']
            oc_id_node = f"oc_{oc_id}"
            # Ajustar URL a la ruta real: /compras/detalle/<id>
            nodes.append({"id": oc_id_node, "label": f"OC: {oc_codigo}", "group": "orden_compra", "url": f"/compras/detalle/{oc_id}"})
            edges.append({"from": oc_id_node, "to": li_id_node, "label": lote_insumo.get('cantidad_ingresada', 1)})

        for op in ops_usadas:
            op_id_node = f"op_{op['id']}"
            # Ruta real de detalle OP: /ordenes/<id>/detalle
            nodes.append({"id": op_id_node, "label": f"OP: {op['codigo']}", "group": "orden_produccion", "url": f"/ordenes/{op['id']}/detalle"})
            edges.append({"from": li_id_node, "to": op_id_node, "label": op['cantidad']})

            op_data = next((r for r in reservas if r.get('ordenes_produccion', {}).get('id') == op['id']), None)
            if op_data:
                for lp in op_data.get('ordenes_produccion', {}).get('lotes_productos', []):
                    lp_id_node = f"lp_{lp['id_lote']}"
                    if not any(n['id'] == lp_id_node for n in nodes):
                        # usar numero_lote en etiqueta y cantidad_inicial como cantidad producida
                        # Ruta real de detalle lote producto: /lotes-productos/<id>/detalle
                        nodes.append({"id": lp_id_node, "label": f"LP: {lp.get('numero_lote')}", "group": "lote_producto", "url": f"/lotes-productos/{lp['id_lote']}/detalle"})
                    edges.append({"from": op_id_node, "to": lp_id_node, "label": lp.get('cantidad_inicial', 1)})

        return {"resumen": {"origen": resumen_origen, "uso": resumen_uso}, "riesgo_proveedor": riesgo_proveedor, "diagrama": {"nodes": nodes, "edges": edges}}

    def obtener_trazabilidad_completa_lote_producto(self, lote_id):
        lote_producto_res = self.db.table('lotes_productos').select(
            '*, productos:producto_id(nombre), ordenes_produccion!inner(id, codigo)'
        ).eq('id_lote', lote_id).single().execute()
        lote_producto = lote_producto_res.data
        if not lote_producto: return None

        op_origen = lote_producto.get('ordenes_produccion')
        op_id = op_origen.get('id')

        reservas = self.db.table('reservas_insumos').select(
            'cantidad_reservada, insumos_inventario!inner(*, insumos_catalogo:id_insumo(nombre, unidad_medida), proveedores:id_proveedor(nombre))'
        ).eq('orden_produccion_id', op_id).execute().data

        # En la tabla de pedidos los campos se llaman id_pedido y codigo_pedido
        # La tabla pedidos expone 'id' (sin codigo), ajustar el inner join en consecuencia
        reservas_producto = self.db.table('reservas_productos').select(
            'cantidad_reservada, pedidos!inner(id)'
        ).eq('lote_producto_id', lote_id).execute().data
        
        resumen_origen = {
            "op": {"id": op_id, "codigo": op_origen.get('codigo')},
            "insumos": [
                {
                    "id": r.get('insumos_inventario', {}).get('id_lote'),
                    "nombre": r.get('insumos_inventario', {}).get('insumos_catalogo', {}).get('nombre', 'N/A'),
                    "cantidad": r.get('cantidad_reservada')
                } for r in reservas
            ]
        }
        
        resumen_destino = {
            "pedidos": [
                {
                    # La tabla de pedidos solo tiene 'id' y no tiene 'codigo'
                    "id": r.get('pedidos', {}).get('id'),
                    "codigo": None,
                    "cantidad": r.get('cantidad')
                } for r in reservas_producto
            ]
        }
        
        nodes, edges = [], []
        lp_id_node = f"lp_{lote_id}"
        # usar numero_lote y cantidad_inicial según esquema
        lp_codigo = lote_producto.get('numero_lote')

        # Nodo de lote de producto
        nodes.append({"id": lp_id_node, "label": f"LP: {lp_codigo}", "group": "lote_producto", "url": f"/lotes-productos/{lote_id}/detalle"})

        # Nodo de OP origen
        op_id_node = f"op_{op_id}"
        nodes.append({"id": op_id_node, "label": f"OP: {op_origen.get('codigo')}", "group": "orden_produccion", "url": f"/ordenes/{op_id}/detalle"})
        edges.append({"from": op_id_node, "to": lp_id_node, "label": lote_producto.get('cantidad_inicial', 1)})

        # Insumos usados por la OP (entradas hacia la OP)
        for r in reservas:
            insumo = r.get('insumos_inventario', {})
            li_id = insumo.get('id_lote')
            li_id_node = f"li_{li_id}"
            insumo_nombre = insumo.get('insumos_catalogo', {}).get('nombre', 'N/A')
            if not any(n['id'] == li_id_node for n in nodes):
                nodes.append({"id": li_id_node, "label": f"LI: {insumo_nombre}", "group": "lote_insumo", "url": f"/inventario/lote/{li_id}"})
            edges.append({"from": li_id_node, "to": op_id_node, "label": r.get('cantidad_reservada')})

        # Pedidos relacionados con el lote de producto (salidas desde LP)
        for r in reservas_producto:
            pedido = r.get('pedidos', {})
            ped_id = pedido.get('id')
            ped_id_node = f"ped_{ped_id}"
            if not any(n['id'] == ped_id_node for n in nodes):
                # Ruta real pedido /orden-venta/<id>/detalle
                nodes.append({"id": ped_id_node, "label": f"PED: {ped_id}", "group": "pedido", "url": f"/orden-venta/{ped_id}/detalle"})
            edges.append({"from": lp_id_node, "to": ped_id_node, "label": r.get('cantidad')})

        return {
            "resumen": {"origen": resumen_origen, "destino": resumen_destino},
            "diagrama": {"nodes": nodes, "edges": edges}
        }

    def obtener_trazabilidad_completa_orden_produccion(self, orden_id):
        """
        Construye la trazabilidad completa para una Orden de Producción (OP).
        Incluye insumos utilizados (lotes insumo), lotes de producto generados y pedidos relacionados.
        """
        op_res = self.db.table('ordenes_produccion').select(
            '*, supervisor:supervisor_responsable_id(nombre, apellido), lotes_productos!orden_produccion_id(id_lote, numero_lote, cantidad_inicial)'
        ).eq('id', orden_id).single().execute()
        op = op_res.data
        if not op: return None
        
        # --- Lógica para obtener supervisor de calidad por separado ---
        if op.get('supervisor_calidad_id'):
            sv_calidad_res = self.db.table('usuarios').select('nombre, apellido').eq('id', op['supervisor_calidad_id']).single().execute()
            if sv_calidad_res.data:
                sv_info = sv_calidad_res.data
                op['supervisor_calidad_nombre'] = f"{sv_info.get('nombre', '')} {sv_info.get('apellido', '')}".strip()
            else:
                op['supervisor_calidad_nombre'] = 'No encontrado'
        else:
            op['supervisor_calidad_nombre'] = 'No asignado'
        # --- Fin de la nueva lógica ---

        # Insumos reservados para la OP
        reservas_insumos = self.db.table('reservas_insumos').select(
            'cantidad_reservada, insumos_inventario!inner(*, insumos_catalogo:id_insumo(nombre), proveedores:id_proveedor(nombre))'
        ).eq('orden_produccion_id', orden_id).execute().data

        # Lotes de producto generados por la OP
        lotes_producto = op.get('lotes_productos', [])
        lote_ids = [lp.get('id_lote') for lp in lotes_producto if lp.get('id_lote')]

        reservas_productos = []
        if lote_ids:
            # La tabla pedidos solo expone 'id' (sin codigo), solicitar id y el lote relacionado
            reservas_productos = self.db.table('reservas_productos').select('cantidad, pedidos!inner(id, lote_producto_id)').in_('lote_producto_id', lote_ids).execute().data

        resumen_origen = {
            'op': {'id': orden_id, 'codigo': op.get('codigo')},
            'insumos': [
                {
                    'id': r.get('insumos_inventario', {}).get('id_lote'),
                    'nombre': r.get('insumos_inventario', {}).get('insumos_catalogo', {}).get('nombre', 'N/A'),
                    'cantidad': r.get('cantidad_reservada')
                } for r in reservas_insumos
            ]
        }
        resumen_destino = {
            'lotes': [{'id': lp.get('id_lote'), 'codigo': lp.get('numero_lote'), 'cantidad': lp.get('cantidad_inicial')} for lp in lotes_producto],
            'pedidos': [
                {'id': r.get('pedidos', {}).get('id'), 'codigo': None, 'cantidad': r.get('cantidad'), 'lote_producto_id': r.get('lote_producto_id')}
                for r in reservas_productos
            ]
        }

        nodes, edges = [], []
        op_node = f"op_{orden_id}"
        nodes.append({'id': op_node, 'label': f"OP: {op.get('codigo')}", 'group': 'orden_produccion', 'url': f"/ordenes/{orden_id}/detalle"})

        # Lotes de producto (salidas)
        for lp in lotes_producto:
            lp_id = lp.get('id_lote')
            if lp_id:
                lp_node = f"lp_{lp_id}"
                if not any(n['id'] == lp_node for n in nodes):
                    nodes.append({'id': lp_node, 'label': f"LP: {lp.get('numero_lote')}", 'group': 'lote_producto', 'url': f"/lotes-productos/{lp_id}/detalle"})
                edges.append({'from': op_node, 'to': lp_node, 'label': lp.get('cantidad_inicial', 1)})

        # Insumos (entradas)
        for r in reservas_insumos:
            ins = r.get('insumos_inventario', {})
            li_id = ins.get('id_lote')
            if li_id:
                li_node = f"li_{li_id}"
                if not any(n['id'] == li_node for n in nodes):
                    nodes.append({'id': li_node, 'label': f"LI: {ins.get('insumos_catalogo', {}).get('nombre', 'N/A')}", 'group': 'lote_insumo', 'url': f"/inventario/lote/{li_id}"})
                edges.append({'from': li_node, 'to': op_node, 'label': r.get('cantidad_reservada')})

        # Pedidos relacionados
        for r in reservas_productos:
            ped = r.get('pedidos', {})
            ped_id = ped.get('id')
            if ped_id:
                ped_node = f"ped_{ped_id}"
                if not any(n['id'] == ped_node for n in nodes):
                    nodes.append({'id': ped_node, 'label': f"PED: {ped_id}", 'group': 'pedido', 'url': f"/orden-venta/{ped_id}/detalle"})
                # conectar desde cada LP correspondiente hacia el pedido
                lote_rel = r.get('lote_producto_id')
                if lote_rel:
                    lp_node = f"lp_{lote_rel}"
                    edges.append({'from': lp_node, 'to': ped_node, 'label': r.get('cantidad')})
                else:
                    edges.append({'from': op_node, 'to': ped_node, 'label': r.get('cantidad')})

        return {'resumen': {'origen': resumen_origen, 'destino': resumen_destino}, 'diagrama': {'nodes': nodes, 'edges': edges}}

    @classmethod
    def get_table_name(cls):
        return None

    @classmethod
    def get_id_column(cls):
        return None
