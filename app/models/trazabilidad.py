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
            # rechazados_res = self.db.table('insumos_inventario').select(
            #     'id_lote', count='exact'
            # ).eq('id_proveedor', proveedor_id).eq('estado_calidad', 'Rechazado').execute()
            # lotes_rechazados = rechazados_res.count or 0
            lotes_rechazados= 0
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
            try:
                oc_res = self.db.table('ordenes_compra').select('id, codigo_oc').eq('codigo_oc', codigo_oc).single().execute()
                orden_compra = oc_res.data
            except APIError as e:
                if e.code == 'PGRST116': # No rows found
                    orden_compra = None
                else:
                    raise e # Re-raise other API errors
        
        proveedor_id = lote_insumo.get('id_proveedor')
        riesgo_proveedor = self._obtener_riesgo_proveedor(proveedor_id)
        
        resumen_origen = {
            "insumo": lote_insumo.get('insumos_catalogo', {}).get('nombre', 'N/A'),
            "proveedor": lote_insumo.get('proveedores', {}).get('nombre', 'N/A'),
            "lote_proveedor": lote_insumo.get('numero_lote_proveedor', 'N/A'),
            "orden_compra": {"id": orden_compra.get('id'), "codigo": orden_compra.get('codigo_oc')} if orden_compra else None,
            "recepcion": lote_insumo.get('fecha_ingreso', 'N/A'),
            "calidad": lote_insumo.get('estado_calidad', 'Pendiente')
        }

        ops_usadas = []
        productos_generados = []
        pedidos_asociados=[]
        op_id = lote_insumo.get('orden_produccion_id')
        if op_id:
            op_res = self.db.table('ordenes_produccion').select('id, codigo').eq('id', op_id).maybe_single().execute()
            op = op_res.data
            if op:
                ops_usadas.append({
                    "id": op['id'], 
                    "codigo": op['codigo'],
                    "cantidad": lote_insumo.get('cantidad_inicial') # La cantidad usada es la total del lote
                })
                # Buscar lotes de producto de esta OP
                lotes_prod_res = self.db.table('lotes_productos').select('id_lote, numero_lote, cantidad_inicial').eq('orden_produccion_id', op_id).execute()
                lotes_producto = lotes_prod_res.data or []
                for lp in lotes_producto:
                    productos_generados.append({"id": lp.get('id_lote'), "codigo": lp.get('numero_lote')})
        
            lote_producto_ids = [lp['id'] for lp in productos_generados]
            if lote_producto_ids:
                reservas_prod_res = self.db.table('reservas_productos').select('pedidos!inner(id, nombre_cliente)').in_('lote_producto_id', lote_producto_ids).execute()
                for r in (reservas_prod_res.data or []):
                    if r.get('pedidos'):
                        pedidos_asociados.append({
                                "id": r['pedidos']['id'],
                                "cliente": r['pedidos'].get('nombre_cliente', 'N/A')
                        })

        resumen_uso = {
            "ops": ops_usadas,
            "productos": productos_generados,
            "pedidos": list({p['id']: p for p in pedidos_asociados}.values()) # Eliminar duplicados
        }
        
        nodes, edges = [], []
        li_id_node = f"li_{lote_insumo['id_lote']}"
        nodes.append({"id": li_id_node, "label": f"LI: {resumen_origen['insumo']}", "group": "lote_insumo", "url": f"/inventario/lote/{lote_insumo['id_lote']}"})

        if resumen_origen.get('orden_compra'):
            oc = resumen_origen['orden_compra']
            oc_id_node = f"oc_{oc['id']}"
            nodes.append({"id": oc_id_node, "label": f"OC: {oc['codigo']}", "group": "orden_compra", "url": f"/compras/detalle/{oc['id']}"})
            edges.append({"from": oc_id_node, "to": li_id_node, "label": str(lote_insumo.get('cantidad_ingresada', ''))})

        if ops_usadas:
            op = ops_usadas[0]
            op_id_node = f"op_{op['id']}"
            nodes.append({"id": op_id_node, "label": f"OP: {op['codigo']}", "group": "orden_produccion", "url": f"/ordenes/{op['id']}/detalle"})
            edges.append({"from": li_id_node, "to": op_id_node, "label": str(op.get('cantidad', ''))})


            if productos_generados:
                lote_ids = [lp['id'] for lp in productos_generados]
                lotes_prod_details_res = self.db.table('lotes_productos').select('id_lote, numero_lote, cantidad_inicial').in_('id_lote', lote_ids).execute()
                for lp in (lotes_prod_details_res.data or []):
                    lp_id_node = f"lp_{lp['id_lote']}"
                    nodes.append({"id": lp_id_node, "label": f"LP: {lp['numero_lote']}", "group": "lote_producto", "url": f"/lotes-productos/{lp['id_lote']}/detalle"})
                    edges.append({"from": op_id_node, "to": lp_id_node, "label": str(lp.get('cantidad_inicial', ''))})
                if pedidos_asociados:
                    pedidos_ids = [p['id'] for p in pedidos_asociados]
                    reservas_pedidos_res = self.db.table('reservas_productos').select(
                        'cantidad_reservada, lote_producto_id, pedidos!inner(id)'
                    ).in_('lote_producto_id', lote_ids).in_('pedido_id', pedidos_ids).execute()
                    
                    pedidos_nodes_added = set()
                    for r in (reservas_pedidos_res.data or []):
                        if not r.get('pedidos'): continue
                        ped_id = r['pedidos']['id']
                        ped_id_node = f"ped_{ped_id}"
                        if ped_id not in pedidos_nodes_added:
                            nodes.append({"id": ped_id_node, "label": f"PED: #{ped_id}", "group": "pedido", "url": f"/orden-venta/{ped_id}/detalle"})
                            pedidos_nodes_added.add(ped_id)
                        
                        lp_origen_node = f"lp_{r['lote_producto_id']}"
                        edges.append({"from": lp_origen_node, "to": ped_id_node, "label": str(r.get('cantidad_reservada', ''))})

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
            'cantidad_reservada, insumos_inventario!inner(*, insumos_catalogo:id_insumo(nombre, unidad_medida), proveedores!inner(id, nombre))'
        ).eq('orden_produccion_id', op_id).execute().data
        
        reservas_producto = self.db.table('reservas_productos').select(
            'cantidad_reservada, pedidos!inner(id, clientes!inner(id, razon_social))'
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
                     "codigo": f"PED-{r.get('pedidos', {}).get('id')}",
                    "cantidad": r.get('cantidad_reservada')
                } for r in reservas_producto if r.get('pedidos')
            ]
        }
        
        nodes, edges = [], []
        lp_id_node = f"lp_{lote_id}"
        # usar numero_lote y cantidad_inicial según esquema
        lp_codigo = lote_producto.get('numero_lote')

        # Nodo de lote de producto
        lp_producto_nombre = lote_producto.get('productos', {}).get('nombre', 'N/A')
        lp_fecha_vencimiento = lote_producto.get('fecha_vencimiento', 'N/A')
        nodes.append({
            "id": lp_id_node,
            "label": f"LP: {lp_codigo}",
            "group": "lote_producto",
            "title": (f"<strong>Lote Producto:</strong> {lp_codigo}<br>"
                      f"<strong>Producto:</strong> {lp_producto_nombre}<br>"
                      f"<strong>Cantidad Producida:</strong> {lote_producto.get('cantidad_inicial', 'N/A')}<br>"
                      f"<strong>Fecha Vencimiento:</strong> {lp_fecha_vencimiento}"),
            "url": f"/lotes-productos/{lote_id}/detalle"
        })

        # Nodo de OP origen
        op_id_node = f"op_{op_id}"
        op_cantidad_planificada = op_origen.get('cantidad_planificada', 'N/A')
        nodes.append({
            "id": op_id_node,
            "label": f"OP: {op_origen.get('codigo')}",
            "group": "orden_produccion",
            "title": (f"<strong>Orden de Producción:</strong> {op_origen.get('codigo')}<br>"
                      f"<strong>Cantidad Planificada:</strong> {op_cantidad_planificada}"),
            "url": f"/ordenes/{op_id}/detalle"
        })

        edges.append({"from": op_id_node, "to": lp_id_node, "label": lote_producto.get('cantidad_inicial', 1)})

        # Insumos usados por la OP (entradas hacia la OP)
        for r in reservas:
            insumo = r.get('insumos_inventario', {})
            if not insumo: continue
            li_id = insumo.get('id_lote')
            li_id_node = f"li_{li_id}"
            insumo_nombre = insumo.get('insumos_catalogo', {}).get('nombre', 'N/A')
            
            # Buscar la Orden de Compra asociada
            oc_node_id = None
            codigo_oc = insumo.get('documento_ingreso')
            if codigo_oc:
                oc_res = self.db.table('ordenes_compra').select('id, codigo_oc').eq('codigo_oc', codigo_oc).maybe_single().execute()
                if oc_res.data:
                    oc = oc_res.data
                    oc_node_id = f"oc_{oc['id']}"
                    if not any(n['id'] == oc_node_id for n in nodes):
                        nodes.append({
                            "id": oc_node_id,
                            "label": f"OC: {oc['codigo_oc']}",
                            "group": "orden_compra",
                            "title": f"<strong>Orden de Compra:</strong> {oc['codigo_oc']}",
                            "url": f"/compras/detalle/{oc['id']}"
                        })

            if not any(n['id'] == li_id_node for n in nodes):
                proveedor_info = insumo.get('proveedores', {}) or {}
                proveedor_nombre = proveedor_info.get('nombre', 'N/A')
                proveedor_nro = proveedor_info.get('id', 'N/A')
                
                tooltip = (f"<strong>Lote Insumo:</strong> {insumo.get('numero_lote_proveedor', 'N/A')}<br>"
                           f"<strong>Insumo:</strong> {insumo_nombre}<br>"
                           f"<strong>Cantidad Usada:</strong> {r.get('cantidad_reservada', 'N/A')}<br>"
                           f"<strong>Proveedor:</strong> {proveedor_nombre} (Nro: {proveedor_nro})")

                nodes.append({
                    "id": li_id_node,
                    "label": f"LI: {insumo_nombre}",
                    "group": "lote_insumo",
                    "title": tooltip,
                    "url": f"/inventario/lote/{li_id}"})
            
            # Crear edge desde OC a Lote de Insumo (si existe)
            if oc_node_id:
                 edges.append({"from": oc_node_id, "to": li_id_node, "label": insumo.get('cantidad_ingresada')})

            edges.append({"from": li_id_node, "to": op_id_node, "label": r.get('cantidad_reservada')})

        # Pedidos relacionados con el lote de producto (salidas desde LP)
        for r in reservas_producto:
            pedido = r.get('pedidos', {})
            if not pedido: continue

            ped_id = pedido.get('id')
            ped_id_node = f"ped_{ped_id}"
            if not any(n['id'] == ped_id_node for n in nodes):
                cliente_nombre = pedido.get('clientes', {}).get('razon_social', 'N/A')
                tooltip = (f"<strong>Pedido:</strong> {ped_id}<br>"
                           f"<strong>Cliente:</strong> {cliente_nombre}<br>"
                           f"<strong>Cantidad Despachada:</strong> {r.get('cantidad_reservada', 'N/A')}")

                nodes.append({
                    "id": ped_id_node,
                    "label": f"PED: {ped_id}",
                    "group": "pedido",
                    "title": tooltip,
                    "url": f"/orden-venta/{ped_id}/detalle"
                })
            edges.append({"from": lp_id_node, "to": ped_id_node, "label": r.get('cantidad_reservada')})

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
            '*, producto:producto_id(nombre), supervisor:supervisor_responsable_id(nombre, apellido)'
        ).eq('id', orden_id).single().execute()
        op = op_res.data
        if not op: return None
                # 2. Trazabilidad Ascendente (Upstream) - LÓGICA CORRECTA
        insumos_usados_res = self.db.table('insumos_inventario').select(
            'id_lote, numero_lote_proveedor, cantidad_inicial, documento_ingreso, '
            'insumo:id_insumo(nombre), '
            'proveedor:id_proveedor(id, nombre)'
        ).eq('orden_produccion_id', orden_id).execute()
        insumos_usados = insumos_usados_res.data or []
        
        # OCs directamente asociadas a la OP (para casos sin lote intermedio)
        ocs_directas_res = self.db.table('ordenes_compra').select(
            '*, proveedores:proveedor_id(id, nombre)'
        ).eq('orden_produccion_id', orden_id).execute()
        ocs_asociadas_directamente = ocs_directas_res.data or []


        # 3. Trazabilidad Descendente (Downstream)
        lotes_producto_res = self.db.table('lotes_productos').select(
            'id_lote, numero_lote, cantidad_inicial, fecha_vencimiento, producto:producto_id(nombre)'
        ).eq('orden_produccion_id', orden_id).execute()
        lotes_producto = lotes_producto_res.data or []
        lote_ids = [lp['id_lote'] for lp in lotes_producto]

        pedidos_info = {}

        reservas_productos = []
        if lote_ids:
            reservas_prod_res = self.db.table('reservas_productos').select(
                'cantidad_reservada, lote_producto_id, pedido:pedidos!inner(id, nombre_cliente, fecha_requerido)'
            ).in_('lote_producto_id', lote_ids).execute()
            reservas_productos = reservas_prod_res.data or []
            for r in reservas_productos:
                p = r.get('pedido')
                if p and p.get('id') not in pedidos_info:
                    pedidos_info[p['id']] = p

        # --- Construcción de Resumen ---
        resumen_insumos = [{
            'id': insumo.get('id_lote'),
            'nombre': insumo.get('insumo', {}).get('nombre', 'N/A'),
            'lote_proveedor': insumo.get('numero_lote_proveedor'),
            'proveedor': insumo.get('proveedor', {}).get('nombre', 'N/A'),
            'cantidad': insumo.get('cantidad_inicial'),
        } for insumo in insumos_usados]
        
        resumen_ocs_asociadas = [{
            'id': oc.get('id'),
            'codigo_oc': oc.get('codigo_oc'),
            'proveedor_nombre': oc.get('proveedores', {}).get('nombre', 'N/A'),
            'estado': oc.get('estado')
        } for oc in ocs_asociadas_directamente]
        
        resumen_origen = {
            'op': {'id': orden_id, 'codigo': op.get('codigo'), 'producto': op.get('producto', {}).get('nombre'), 'cantidad': op.get('cantidad_planificada')},
            'insumos_utilizados': resumen_insumos,
            'ocs_asociadas': resumen_ocs_asociadas
        }
        
        resumen_destino = {
           'lotes_producidos': [{'id': lp.get('id_lote'), 'codigo': lp.get('numero_lote'), 'cantidad': lp.get('cantidad_inicial')} for lp in lotes_producto],
            'pedidos_relacionados': [{'id': pid, 'cliente': pinfo.get('nombre_cliente', 'N/A')} for pid, pinfo in pedidos_info.items()]
        }

        nodes, edges = [], []
        op_node = f"op_{orden_id}"
        op_title = f"<strong>OP:</strong> {op.get('codigo')}<br><strong>Producto:</strong> {op.get('producto', {}).get('nombre')}<br><strong>Cantidad:</strong> {op.get('cantidad_planificada')}"
        nodes.append({'id': op_node, 'label': f"OP: {op.get('codigo')}", 'group': 'orden_produccion', 'title': op_title, 'url': f"/ordenes/{orden_id}/detalle"})

        # Nodos y Ejes: Upstream
        for insumo in insumos_usados:
            li_id, li_node = insumo['id_lote'], f"li_{insumo['id_lote']}"
            if not any(n['id'] == li_node for n in nodes):
                li_title = f"<strong>Lote Insumo:</strong> {insumo.get('numero_lote_proveedor', 'N/A')}<br><strong>Insumo:</strong> {insumo.get('insumo', {}).get('nombre', 'N/A')}<br><strong>Proveedor:</strong> {insumo.get('proveedor', {}).get('nombre', 'N/A')}"
                nodes.append({'id': li_node, 'label': f"LI: {insumo.get('insumo', {}).get('nombre', 'N/A')}", 'group': 'lote_insumo', 'title': li_title, 'url': f"/inventario/lote/{li_id}"})
            
            edges.append({'from': li_node, 'to': op_node, 'label': str(insumo.get('cantidad_inicial'))})
            codigo_oc = insumo.get('documento_ingreso')
            if codigo_oc:
                oc_res = self.db.table('ordenes_compra').select('id, codigo_oc').eq('codigo_oc', codigo_oc).maybe_single().execute()
                if oc_res.data:
                        
                    oc = oc_res.data
                    oc_node = f"oc_{oc['id']}"
                    if not any(n['id'] == oc_node for n in nodes):
                        nodes.append({'id': oc_node, 'label': f"OC: {oc['codigo_oc']}", 'group': 'orden_compra', 'url': f"/compras/detalle/{oc['id']}"})
                    if not any(e['from'] == oc_node and e['to'] == li_node for e in edges):
                        edges.append({'from': oc_node, 'to': li_node, 'label': str(insumo.get('cantidad_inicial'))}) # Asumimos que la OC es por la cantidad del lote

        # Nodos y Ejes: OCs directas
        for oc in ocs_asociadas_directamente:

                oc_node = f"oc_{oc['id']}"
                if not any(n['id'] == oc_node for n in nodes):
                    nodes.append({'id': oc_node, 'label': f"OC: {oc['codigo_oc']}", 'group': 'orden_compra', 'url': f"/compras/detalle/{oc['id']}"})

                    bridge_node = f"insumo_generico_br_{oc['id']}"
                    nodes.append({'id': bridge_node, 'label': "Insumo (Genérico)", 'group': 'lote_insumo', 'color': {'background':'#cccccc', 'border':'#aaaaaa'}})
                    edges.append({'from': oc_node, 'to': bridge_node})
                    edges.append({'from': bridge_node, 'to': op_node})

        # Nodos y Ejes: Downstream
        for lp in lotes_producto:
            lp_id, lp_node = lp['id_lote'], f"lp_{lp['id_lote']}"
            lp_title = f"<strong>Lote Prod:</strong> {lp.get('numero_lote')}<br><strong>Producto:</strong> {lp.get('producto', {}).get('nombre')}<br><strong>Vto:</strong> {lp.get('fecha_vencimiento')}"
            nodes.append({'id': lp_node, 'label': f"LP: {lp.get('numero_lote')}", 'group': 'lote_producto', 'title': lp_title, 'url': f"/lotes-productos/{lp_id}/detalle"})
            edges.append({'from': op_node, 'to': lp_node, 'label': str(lp.get('cantidad_inicial'))})

        for r in reservas_productos:
            p = r.get('pedido', {})
            if not p: continue
            ped_id, ped_node = p['id'], f"ped_{p['id']}"
            lp_origen_node = f"lp_{r['lote_producto_id']}"
            if not any(n['id'] == ped_node for n in nodes):
                ped_title = f"<strong>Pedido:</strong> {ped_id}<br><strong>Cliente:</strong> {p.get('nombre_cliente', 'N/A')}"
                nodes.append({'id': ped_node, 'label': f"PED: {ped_id}", 'group': 'pedido', 'title': ped_title, 'url': f"/orden-venta/{ped_id}/detalle"})
            edges.append({'from': lp_origen_node, 'to': ped_node, 'label': str(r.get('cantidad_reservada'))})

        return {'resumen': {'origen': resumen_origen, 'destino': resumen_destino}, 'diagrama': {'nodes': nodes, 'edges': edges}}

    @classmethod
    def get_table_name(cls):
        return None

    @classmethod
    def get_id_column(cls):
        return None

    def obtener_lista_afectados(self, tipo_entidad, id_entidad):
        afectados = []
        pid = id_entidad

        if tipo_entidad == 'lote_insumo':
            afectados.append({'tipo_entidad': 'lote_insumo', 'id_entidad': pid})
            res_ops = self.db.table('reservas_insumos').select('orden_produccion_id').eq('lote_inventario_id', pid).execute().data or []
            op_ids = list({r.get('orden_produccion_id') for r in res_ops if r.get('orden_produccion_id')})
            for oid in op_ids:
                afectados.extend(self.obtener_lista_afectados('orden_produccion', oid))

        elif tipo_entidad == 'orden_produccion':
            afectados.append({'tipo_entidad': 'orden_produccion', 'id_entidad': pid})
            res_lps = self.db.table('lotes_productos').select('id_lote').eq('orden_produccion_id', pid).execute().data or []
            lp_ids = list({r.get('id_lote') for r in res_lps if r.get('id_lote')})
            for lid in lp_ids:
                afectados.extend(self.obtener_lista_afectados('lote_producto', lid))

        elif tipo_entidad == 'lote_producto':
            afectados.append({'tipo_entidad': 'lote_producto', 'id_entidad': pid})
            res_ped = self.db.table('reservas_productos').select('pedido_id').eq('lote_producto_id', pid).execute().data or []
            ped_ids = list({r.get('pedido_id') for r in res_ped if r.get('pedido_id')})
            for ped_id in ped_ids:
                afectados.append({'tipo_entidad': 'pedido', 'id_entidad': ped_id})
        
        elif tipo_entidad == 'pedido':
            afectados.append({'tipo_entidad': 'pedido', 'id_entidad': pid})

        # Eliminar duplicados
        seen = set()
        unique = []
        for a in afectados:
            key = (a['tipo_entidad'], a['id_entidad'])
            if key not in seen:
                seen.add(key)
                unique.append(a)
        return unique