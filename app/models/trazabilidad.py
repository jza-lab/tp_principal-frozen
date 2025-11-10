from collections import deque
from app.database import Database

class TrazabilidadModel:
    """
    Servicio unificado para encapsular las consultas complejas de trazabilidad.
    No hereda de BaseModel porque no representa una única tabla, sino que
    orquesta consultas a través de múltiples tablas.
    """
    def __init__(self):
        self.db = Database().client

    def obtener_trazabilidad_unificada(self, tipo_entidad_inicial, id_entidad_inicial, nivel='simple'):
        nodos = {}
        aristas = set()
        id_entidad_inicial_str = str(id_entidad_inicial)

        self._agregar_nodo(nodos, tipo_entidad_inicial, id_entidad_inicial_str)

        # 1. Búsqueda hacia atrás (Upstream)
        cola_atras = deque([(tipo_entidad_inicial, id_entidad_inicial_str)])
        visitados_atras = set([(tipo_entidad_inicial, id_entidad_inicial_str)])
        while cola_atras:
            tipo_actual, id_actual = cola_atras.popleft()
            self._trazar_atras(nodos, aristas, tipo_actual, id_actual, cola_atras, visitados_atras)

        # 2. Búsqueda hacia adelante (Downstream)
        cola_adelante = deque([(tipo_entidad_inicial, id_entidad_inicial_str)])
        visitados_adelante = set([(tipo_entidad_inicial, id_entidad_inicial_str)])
        while cola_adelante:
            tipo_actual, id_actual = cola_adelante.popleft()
            self._trazar_adelante(nodos, aristas, tipo_actual, id_actual, cola_adelante, visitados_adelante)

        nodos_filtrados, aristas_filtradas = self._filtrar_grafo_por_nivel(nodos, aristas, tipo_entidad_inicial, id_entidad_inicial_str, nivel)

        # 3. ENRIQUECIMIENTO DE DATOS Y FORMATEO FINAL
        self._enriquecer_datos_nodos(nodos_filtrados)
        
        resumen = self._generar_resumen(nodos_filtrados, aristas_filtradas, tipo_entidad_inicial, id_entidad_inicial)
        diagrama = self._generar_diagrama(nodos_filtrados, aristas_filtradas)

        return {'resumen': resumen, 'diagrama': diagrama}

    # --- MÉTODOS AUXILIARES DE TRAZABILIDAD ---
    def _trazar_atras(self, nodos, aristas, tipo_actual, id_actual, cola, visitados):
        if tipo_actual == 'pedido':
            reservas = self.db.table('reservas_productos').select('lote_producto_id, cantidad_reservada').eq('pedido_id', id_actual).execute().data or []
            for r in reservas:
                self._agregar_nodo_y_arista(nodos, aristas, 'lote_producto', str(r['lote_producto_id']), tipo_actual, id_actual, r['cantidad_reservada'], cola, visitados)
        elif tipo_actual == 'lote_producto':
            lote = self.db.table('lotes_productos').select('orden_produccion_id, cantidad_inicial').eq('id_lote', id_actual).maybe_single().execute().data
            if lote and lote.get('orden_produccion_id'):
                self._agregar_nodo_y_arista(nodos, aristas, 'orden_produccion', str(lote['orden_produccion_id']), tipo_actual, id_actual, lote['cantidad_inicial'], cola, visitados)
        elif tipo_actual == 'orden_produccion':
            reservas = self.db.table('reservas_insumos').select('lote_inventario_id, cantidad_reservada').eq('orden_produccion_id', id_actual).execute().data or []
            for r in reservas:
                 self._agregar_nodo_y_arista(nodos, aristas, 'lote_insumo', str(r['lote_inventario_id']), tipo_actual, id_actual, r['cantidad_reservada'], cola, visitados)
        elif tipo_actual == 'lote_insumo':
            insumo = self.db.table('insumos_inventario').select('documento_ingreso, cantidad_inicial').eq('id_lote', id_actual).maybe_single().execute().data
            if insumo and insumo.get('documento_ingreso'):
                oc = self.db.table('ordenes_compra').select('id').eq('codigo_oc', insumo['documento_ingreso']).maybe_single().execute().data
                if oc:
                    self._agregar_nodo_y_arista(nodos, aristas, 'orden_compra', str(oc['id']), tipo_actual, id_actual, insumo['cantidad_inicial'], cola, visitados)

    def _trazar_adelante(self, nodos, aristas, tipo_actual, id_actual, cola, visitados):
        if tipo_actual == 'orden_compra':
            oc = self.db.table('ordenes_compra').select('codigo_oc').eq('id', id_actual).maybe_single().execute().data
            if oc and oc.get('codigo_oc'):
                insumos = self.db.table('insumos_inventario').select('id_lote, cantidad_inicial').eq('documento_ingreso', oc['codigo_oc']).execute().data or []
                for i in insumos:
                    self._agregar_nodo_y_arista(nodos, aristas, tipo_actual, id_actual, 'lote_insumo', str(i['id_lote']), i['cantidad_inicial'], cola, visitados)
        elif tipo_actual == 'lote_insumo':
            reservas = self.db.table('reservas_insumos').select('orden_produccion_id, cantidad_reservada').eq('lote_inventario_id', id_actual).execute().data or []
            for r in reservas:
                self._agregar_nodo_y_arista(nodos, aristas, tipo_actual, id_actual, 'orden_produccion', str(r['orden_produccion_id']), r['cantidad_reservada'], cola, visitados)
        elif tipo_actual == 'orden_produccion':
            lotes = self.db.table('lotes_productos').select('id_lote, cantidad_inicial').eq('orden_produccion_id', id_actual).execute().data or []
            for l in lotes:
                self._agregar_nodo_y_arista(nodos, aristas, tipo_actual, id_actual, 'lote_producto', str(l['id_lote']), l['cantidad_inicial'], cola, visitados)
        elif tipo_actual == 'lote_producto':
            reservas = self.db.table('reservas_productos').select('pedido_id, cantidad_reservada').eq('lote_producto_id', id_actual).execute().data or []
            for r in reservas:
                self._agregar_nodo_y_arista(nodos, aristas, tipo_actual, id_actual, 'pedido', str(r['pedido_id']), r['cantidad_reservada'], cola, visitados)

    # --- MÉTODOS AUXILIARES GENERALES ---
    def _agregar_nodo(self, nodos, tipo, id, data=None, es_generico=False):
        if (tipo, id) not in nodos:
            nodos[(tipo, id)] = {'data': data, 'es_generico': es_generico}
    
    def _agregar_arista(self, aristas, tipo_origen, id_origen, tipo_destino, id_destino, cantidad):
        cantidad_numerica = cantidad if cantidad is not None and cantidad != '' else 0
        aristas.add(((tipo_origen, id_origen), (tipo_destino, id_destino), cantidad_numerica))

    def _agregar_nodo_y_arista(self, nodos, aristas, tipo_origen, id_origen, tipo_destino, id_destino, cantidad, cola, visitados):
        nodo_origen = (tipo_origen, id_origen)
        nodo_destino = (tipo_destino, id_destino)
        
        self._agregar_nodo(nodos, tipo_origen, id_origen)
        self._agregar_nodo(nodos, tipo_destino, id_destino)
        self._agregar_arista(aristas, tipo_origen, id_origen, tipo_destino, id_destino, cantidad)
        
        # El nodo a explorar es el que está en la dirección de la búsqueda actual.
        # Si la arista va de 'lote' a 'pedido', y estamos trazando hacia atrás, el siguiente nodo a explorar es 'lote'.
        # Si estamos trazando hacia adelante, sería 'pedido'.
        # Como _trazar_atras y _trazar_adelante gestionan su propia lógica, el nodo a añadir a la cola
        # es el que no es el 'actual' en esa función.
        
        # En _trazar_atras, el nodo_destino es el 'actual', así que exploramos el nodo_origen.
        if nodo_origen not in visitados:
            cola.append(nodo_origen)
            visitados.add(nodo_origen)

        # En _trazar_adelante, el nodo_origen es el 'actual', así que exploramos el nodo_destino.
        if nodo_destino not in visitados:
            cola.append(nodo_destino)
            visitados.add(nodo_destino)

    def _agregar_origen_manual(self, nodos, aristas, tipo_lote, id_lote):
        """Crea un nodo de Ingreso Manual y lo conecta como origen."""
        id_manual = 'ingreso_manual'
        self._agregar_nodo(nodos, 'ingreso_manual', id_manual, {'nombre': 'Ingreso Manual'})
        self._agregar_arista(aristas, 'ingreso_manual', id_manual, tipo_lote, id_lote, '')

    def _filtrar_grafo_por_nivel(self, nodos_todos, aristas_todas, tipo_entidad_inicial, id_entidad_inicial, nivel):
        """Filtra los nodos y aristas según el nivel de trazabilidad solicitado."""
        if nivel == 'completo':
            return nodos_todos, aristas_todas
        
        # Lógica para 'simple': solo la cadena directa
        nodos_filtrados = {}
        aristas_filtradas = set()
        
        # Hacia atrás
        camino_atras = self._encontrar_camino_directo(aristas_todas, tipo_entidad_inicial, id_entidad_inicial, 'atras')
        # Hacia adelante
        camino_adelante = self._encontrar_camino_directo(aristas_todas, tipo_entidad_inicial, id_entidad_inicial, 'adelante')

        camino_aristas = camino_atras.union(camino_adelante)
        
        for arista in camino_aristas:
            origen, destino, cantidad = arista
            aristas_filtradas.add(arista)
            if origen not in nodos_filtrados:
                nodos_filtrados[origen] = nodos_todos[origen]
            if destino not in nodos_filtrados:
                nodos_filtrados[destino] = nodos_todos[destino]
        
        # Asegurarse de que el nodo inicial esté si no tiene aristas
        if not nodos_filtrados and (tipo_entidad_inicial, id_entidad_inicial) in nodos_todos:
            nodos_filtrados[(tipo_entidad_inicial, id_entidad_inicial)] = nodos_todos[(tipo_entidad_inicial, id_entidad_inicial)]

        return nodos_filtrados, aristas_filtradas

    def _encontrar_camino_directo(self, aristas, tipo_entidad, id_entidad, direccion):
        """Encuentra recursivamente el camino de aristas en una dirección."""
        camino = set()
        nodo_actual = (tipo_entidad, id_entidad)
        
        if direccion == 'atras':
            aristas_relevantes = [a for a in aristas if a[1] == nodo_actual]
            for a in aristas_relevantes:
                camino.add(a)
                camino.update(self._encontrar_camino_directo(aristas, a[0][0], a[0][1], 'atras'))
        
        elif direccion == 'adelante':
            aristas_relevantes = [a for a in aristas if a[0] == nodo_actual]
            for a in aristas_relevantes:
                camino.add(a)
                camino.update(self._encontrar_camino_directo(aristas, a[1][0], a[1][1], 'adelante'))

        return camino

    def _enriquecer_datos_nodos(self, nodos):
        """
        Obtiene datos detallados de la BD para todos los nodos de forma masiva para evitar el problema N+1.
        """
        # 1. Agrupar IDs por tipo de entidad, asegurándose de que no sean genéricos
        ids_por_tipo = {}
        for (tipo, id), nodo_info in nodos.items():
            if nodo_info.get('es_generico') or tipo == 'ingreso_manual':
                continue
            if tipo not in ids_por_tipo:
                ids_por_tipo[tipo] = []
            ids_por_tipo[tipo].append(id)

        # Mapeo de configuración para cada tipo de entidad
        mapeo_tablas = {
            'orden_compra': {'tabla': 'ordenes_compra', 'id_col': 'id', 'selects': '*, proveedores:proveedor_id(nombre)'},
            'lote_insumo': {'tabla': 'insumos_inventario', 'id_col': 'id_lote', 'selects': '*, insumos_catalogo:id_insumo(nombre)'},
            'orden_produccion': {'tabla': 'ordenes_produccion', 'id_col': 'id', 'selects': '*, productos:producto_id(nombre)'},
            'lote_producto': {'tabla': 'lotes_productos', 'id_col': 'id_lote', 'selects': '*, productos:producto_id(nombre)'},
            'pedido': {'tabla': 'pedidos', 'id_col': 'id', 'selects': '*, clientes:clientes(nombre, razon_social)'}
        }
        
        datos_enriquecidos = {}

        # 2. Realizar una consulta masiva por cada tipo de entidad
        for tipo, ids in ids_por_tipo.items():
            if tipo in mapeo_tablas and ids:
                config = mapeo_tablas[tipo]
                try:
                    # Eliminar duplicados y asegurar que los IDs son del tipo correcto para la consulta
                    ids_unicos = list(set(ids))
                    
                    datos = self.db.table(config['tabla']).select(config['selects']).in_(config['id_col'], ids_unicos).execute().data
                    
                    # Crear un mapa de id -> data para fácil acceso
                    datos_enriquecidos[tipo] = {str(d[config['id_col']]): d for d in datos}

                except Exception as e:
                    print(f"Error al enriquecer nodos de tipo '{tipo}': {e}")
                    datos_enriquecidos[tipo] = {}

        # 3. Asignar los datos enriquecidos de vuelta a la estructura de nodos
        for (tipo, id), nodo_info in nodos.items():
            # Solo asignar si no es genérico y si los datos se encontraron
            if not nodo_info.get('es_generico') and tipo in datos_enriquecidos:
                 nodos[(tipo, id)]['data'] = datos_enriquecidos[tipo].get(str(id), {})


    def _generar_resumen(self, nodos, aristas, tipo_entidad_inicial, id_entidad_inicial):
        """Genera la sección de resumen con listas de origen y destino."""
        resumen = {'origen': [], 'destino': []}
        nodo_inicial = (tipo_entidad_inicial, id_entidad_inicial)

        # Usamos BFS desde el nodo inicial para poblar el resumen
        cola_resumen = deque([nodo_inicial])
        visitados_resumen = {nodo_inicial}

        while cola_resumen:
            tipo_actual, id_actual = cola_resumen.popleft()
            nodo_actual = (tipo_actual, id_actual)
            
            # Origen (hacia atrás)
            aristas_hacia_atras = [a for a in aristas if a[1] == nodo_actual]
            for origen, _, _ in aristas_hacia_atras:
                if origen not in visitados_resumen:
                    nodo_info = nodos.get(origen, {})
                    info_nodo = self._formatear_info_resumen(origen[0], origen[1], nodo_info.get('data'), nodo_info.get('es_generico', False))
                    if info_nodo: resumen['origen'].append(info_nodo)
                    visitados_resumen.add(origen)
                    cola_resumen.append(origen)

            # Destino (hacia adelante)
            aristas_hacia_adelante = [a for a in aristas if a[0] == nodo_actual]
            for _, destino, _ in aristas_hacia_adelante:
                if destino not in visitados_resumen:
                    nodo_info = nodos.get(destino, {})
                    info_nodo = self._formatear_info_resumen(destino[0], destino[1], nodo_info.get('data'), nodo_info.get('es_generico', False))
                    if info_nodo: resumen['destino'].append(info_nodo)
                    visitados_resumen.add(destino)
                    cola_resumen.append(destino)
        
        # Eliminar duplicados
        resumen['origen'] = [dict(t) for t in {tuple(d.items()) for d in resumen['origen']}]
        resumen['destino'] = [dict(t) for t in {tuple(d.items()) for d in resumen['destino']}]

        return resumen

    def _formatear_info_resumen(self, tipo, id, data, es_generico=False):
        """Da formato a la información de un nodo para el resumen."""
        # Excluir nodos genéricos del resumen
        if es_generico:
            return None
            
        if not data: return None
        info = {'tipo': tipo, 'id': id}
        if tipo == 'orden_compra':
            info['nombre'] = data.get('codigo_oc', f'OC-{id}')
            info['detalle'] = f"Proveedor: {data.get('proveedores', {}).get('nombre', 'N/A')}"
        elif tipo == 'lote_insumo':
            info['nombre'] = data.get('insumos_catalogo', {}).get('nombre', 'N/A')
            info['detalle'] = f"Lote: {data.get('numero_lote_proveedor', 'N/A')}"
        elif tipo == 'orden_produccion':
            info['nombre'] = data.get('codigo', f'OP-{id}')
            info['detalle'] = f"Producto: {data.get('productos', {}).get('nombre', 'N/A')}"
        elif tipo == 'lote_producto':
            info['nombre'] = data.get('productos', {}).get('nombre', 'N/A')
            info['detalle'] = f"Lote: {data.get('numero_lote', 'N/A')}"
        elif tipo == 'pedido':
            info['nombre'] = f"Pedido #{id}"
            info['detalle'] = f"Cliente: {data.get('clientes', {}).get('razon_social', 'N/A')}"
        else:
            return None
        return info

    def _generar_diagrama(self, nodos, aristas):
        """Genera la sección de diagrama con formato para Vis.js."""
        nodos_diagrama = []
        urls = {
            'orden_compra': '/compras/detalle/<id>',
            'lote_insumo': '/inventario/lote/<id>',
            'orden_produccion': '/ordenes/<id>/detalle',
            'lote_producto': '/lotes-productos/<id>/detalle',
            'pedido': '/orden-venta/<id>/detalle'
        }

        for (tipo, id), info in nodos.items():
            data = info.get('data', {})
            es_generico = info.get('es_generico', False)
            
            label = f"{tipo.replace('_', ' ').title()}"
            if tipo == 'orden_compra': label = f"OC: {data.get('codigo_oc', id)}"
            elif tipo == 'lote_insumo': label = f"LI: {data.get('insumos_catalogo', {}).get('nombre', 'Genérico')}"
            elif tipo == 'orden_produccion': label = f"OP: {data.get('codigo', id)}"
            elif tipo == 'lote_producto': label = f"LP: {data.get('numero_lote', id)}"
            elif tipo == 'pedido': label = f"Pedido: #{id}"
            elif tipo == 'ingreso_manual': label = "Ingreso Manual"

            nodo_obj = {
                'id': f"{tipo}_{id}",
                'label': label,
                'group': tipo
            }
            if not es_generico and tipo in urls:
                nodo_obj['url'] = urls[tipo].replace('<id>', str(id))
            if es_generico:
                nodo_obj['color'] = {'background':'#cccccc', 'border':'#aaaaaa'}

            nodos_diagrama.append(nodo_obj)
            
        aristas_diagrama = [{
            'from': f"{origen[0]}_{origen[1]}",
            'to': f"{destino[0]}_{destino[1]}",
            'label': str(cantidad)
        } for origen, destino, cantidad in aristas]

        return {'nodes': nodos_diagrama, 'edges': aristas_diagrama}

    def obtener_lista_afectados(self, tipo_entidad_inicial, id_entidad_inicial):
        """
        Obtiene la lista plana de todas las entidades afectadas a partir de un punto,
        utilizando la nueva lógica de trazabilidad unificada.
        """
        resultado_trazabilidad = self.obtener_trazabilidad_unificada(tipo_entidad_inicial, id_entidad_inicial, nivel='completo')
        
        # Los nodos ya están enriquecidos y filtrados, así que son la fuente de verdad.
        nodos_finales = resultado_trazabilidad.get('diagrama', {}).get('nodes', [])
        
        afectados = []
        for nodo in nodos_finales:
            try:
                # El ID del nodo es "tipo_id", necesitamos separar el tipo y el ID.
                tipo, id_entidad = nodo['id'].split('_', 1)
                
                # Omitir nodos genéricos o de ingreso manual que no representan entidades reales de la BD
                if tipo in ['ingreso_manual'] or 'generico' in id_entidad:
                    continue
                
                # Intentar convertir a entero si es posible, si no, mantener como string (para UUIDs)
                try:
                    id_entidad_parsed = int(id_entidad)
                except ValueError:
                    id_entidad_parsed = id_entidad
                    
                afectados.append({'tipo_entidad': tipo, 'id_entidad': id_entidad_parsed})
            except ValueError:
                # Ignorar nodos cuyo ID no sigue el formato esperado
                continue
        
        return afectados

    @classmethod
    def get_table_name(cls):
        return None

    @classmethod
    def get_id_column(cls):
        return None