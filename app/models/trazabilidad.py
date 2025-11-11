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
        """
        Construye y devuelve la red de trazabilidad completa o simple para una entidad dada.

        Args:
            tipo_entidad_inicial (str): El tipo de la entidad de inicio.
            id_entidad_inicial (int): El ID de la entidad de inicio.
            nivel (str): 'simple' para la cadena directa, 'completo' para el grafo total.

        Returns:
            dict: Un diccionario con las secciones 'resumen' y 'diagrama'.
        """
        
        # Estructuras para almacenar el grafo completo
        nodos = {}
        aristas = set()
        
        # Normalizar ID inicial a string para consistencia
        id_entidad_inicial = str(id_entidad_inicial)

        # Estructuras para almacenar el grafo completo
        nodos = {}
        aristas = set()
        
        # Agregar el nodo inicial explícitamente para asegurar que siempre exista
        self._agregar_nodo(nodos, tipo_entidad_inicial, id_entidad_inicial)
        
        # Cola para el algoritmo BFS (Búsqueda en Anchura)
        cola = deque([(tipo_entidad_inicial, id_entidad_inicial)])
        visitados = set([(tipo_entidad_inicial, id_entidad_inicial)])

        # 1. CONSTRUCCIÓN DEL GRAFO COMPLETO (BFS)
        while cola:
            tipo_entidad_actual, id_entidad_actual = cola.popleft()
            
            # Determinar si el ID actual debe ser tratado como un entero
            id_es_numerico = tipo_entidad_actual in ['pedido', 'lote_producto', 'orden_produccion', 'orden_compra']
            
            # --- HACIA ATRÁS (Upstream) ---
            query_id = int(id_entidad_actual) if id_es_numerico else id_entidad_actual
            
            if tipo_entidad_actual == 'pedido':
                # Pedido -> Lote de Producto
                reservas = self.db.table('reservas_productos').select('lote_producto_id, cantidad_reservada').eq('pedido_id', query_id).execute().data or []
                for r in reservas:
                    self._agregar_nodo_y_arista(nodos, aristas, 'lote_producto', str(r['lote_producto_id']), 'pedido', id_entidad_actual, r['cantidad_reservada'], cola, visitados)

            elif tipo_entidad_actual == 'lote_producto':
                # Lote de Producto -> Orden de Producción
                lote = self.db.table('lotes_productos').select('orden_produccion_id, cantidad_inicial').eq('id_lote', query_id).maybe_single().execute().data
                if lote and lote.get('orden_produccion_id'):
                    self._agregar_nodo_y_arista(nodos, aristas, 'orden_produccion', str(lote['orden_produccion_id']), 'lote_producto', id_entidad_actual, lote['cantidad_inicial'], cola, visitados)

            elif tipo_entidad_actual == 'orden_produccion':
                # Orden de Producción -> Lote de Insumo
                reservas = self.db.table('reservas_insumos').select('lote_inventario_id, cantidad_reservada').eq('orden_produccion_id', query_id).execute().data or []
                for r in reservas:
                     self._agregar_nodo_y_arista(nodos, aristas, 'lote_insumo', str(r['lote_inventario_id']), 'orden_produccion', id_entidad_actual, r['cantidad_reservada'], cola, visitados)
                
                # Manejo de OCs directamente asociadas a la OP
                ocs_directas = self.db.table('ordenes_compra').select('id, codigo_oc').eq('orden_produccion_id', query_id).execute().data or []
                for oc in ocs_directas:
                    id_oc_str = str(oc['id'])
                    # Asegurarse de que el nodo de la OC exista antes de crear aristas hacia él.
                    self._agregar_nodo(nodos, 'orden_compra', id_oc_str)
                    
                    # Crear un nodo "puente" genérico para el insumo
                    id_insumo_generico = f"insumo_generico_{id_oc_str}"
                    self._agregar_nodo(nodos, 'lote_insumo', id_insumo_generico, {'numero_lote_proveedor': 'Insumo Genérico', 'insumos_catalogo': {'nombre': 'Genérico'}}, es_generico=True)
                    
                    self._agregar_arista(aristas, 'orden_compra', id_oc_str, 'lote_insumo', id_insumo_generico, '')
                    self._agregar_arista(aristas, 'lote_insumo', id_insumo_generico, 'orden_produccion', id_entidad_actual, '')
                    
                    if ('orden_compra', id_oc_str) not in visitados:
                        cola.append(('orden_compra', id_oc_str))
                        visitados.add(('orden_compra', id_oc_str))


            elif tipo_entidad_actual == 'lote_insumo':
                # Lote de Insumo -> Orden de Compra o Ingreso Manual
                # Un ID de lote de insumo puede ser un UUID (string) o un int del legacy.
                # Solo buscamos en la BD si no es un nodo genérico creado por nosotros.
                if not id_entidad_actual.startswith('insumo_generico_'):
                    insumo = self.db.table('insumos_inventario').select('documento_ingreso, cantidad_inicial').eq('id_lote', id_entidad_actual).maybe_single().execute().data
                    if insumo and insumo.get('documento_ingreso'):
                        oc = self.db.table('ordenes_compra').select('id').eq('codigo_oc', insumo['documento_ingreso']).maybe_single().execute().data
                        if oc:
                            self._agregar_nodo_y_arista(nodos, aristas, 'orden_compra', str(oc['id']), 'lote_insumo', id_entidad_actual, insumo['cantidad_inicial'], cola, visitados)
                        else: # Si el código no corresponde a ninguna OC
                            self._agregar_origen_manual(nodos, aristas, 'lote_insumo', id_entidad_actual)
                    else: # Si no tiene documento
                        self._agregar_origen_manual(nodos, aristas, 'lote_insumo', id_entidad_actual)

            # --- HACIA ADELANTE (Downstream) ---
            if tipo_entidad_actual == 'orden_compra':
                # Orden de Compra -> Lote de Insumo
                oc = self.db.table('ordenes_compra').select('codigo_oc').eq('id', query_id).maybe_single().execute().data
                if oc and oc.get('codigo_oc'):
                    insumos = self.db.table('insumos_inventario').select('id_lote, cantidad_inicial').eq('documento_ingreso', oc['codigo_oc']).execute().data or []
                    for i in insumos:
                        # Corregido: La arista es DESDE la OC HACIA el lote de insumo
                        self._agregar_nodo_y_arista(nodos, aristas, 
                                                  'orden_compra', id_entidad_actual, 
                                                  'lote_insumo', str(i['id_lote']), 
                                                  i['cantidad_inicial'], 
                                                  cola, visitados)

            elif tipo_entidad_actual == 'lote_insumo' and not id_entidad_actual.startswith('insumo_generico_'):
                # Lote de Insumo -> Orden de Producción
                reservas = self.db.table('reservas_insumos').select('orden_produccion_id, cantidad_reservada').eq('lote_inventario_id', query_id).execute().data or []
                for r in reservas:
                    self._agregar_nodo_y_arista(nodos, aristas, 'lote_insumo', id_entidad_actual, 'orden_produccion', str(r['orden_produccion_id']), r['cantidad_reservada'], cola, visitados)
            
            elif tipo_entidad_actual == 'orden_produccion':
                # Orden de Producción -> Lote de Producto
                lotes = self.db.table('lotes_productos').select('id_lote, cantidad_inicial').eq('orden_produccion_id', query_id).execute().data or []
                for l in lotes:
                    self._agregar_nodo_y_arista(nodos, aristas, 'orden_produccion', id_entidad_actual, 'lote_producto', str(l['id_lote']), l['cantidad_inicial'], cola, visitados)

                # Orden de Producción -> Pedido (Vínculo directo a través de pedido_items)
                pedido_items = self.db.table('pedido_items').select('pedido_id, cantidad').eq('orden_produccion_id', query_id).execute().data or []
                pedidos_vinculados = {}
                for item in pedido_items:
                    pedido_id = str(item['pedido_id'])
                    if pedido_id not in pedidos_vinculados:
                        pedidos_vinculados[pedido_id] = 0
                    pedidos_vinculados[pedido_id] += item['cantidad']

                for pedido_id, cantidad_total in pedidos_vinculados.items():
                    self._agregar_nodo_y_arista(nodos, aristas, 'orden_produccion', id_entidad_actual, 'pedido', pedido_id, cantidad_total, cola, visitados)

            elif tipo_entidad_actual == 'lote_producto':
                # Lote de Producto -> Pedido
                reservas = self.db.table('reservas_productos').select('pedido_id, cantidad_reservada').eq('lote_producto_id', query_id).execute().data or []
                for r in reservas:
                    self._agregar_nodo_y_arista(nodos, aristas, 'lote_producto', id_entidad_actual, 'pedido', str(r['pedido_id']), r['cantidad_reservada'], cola, visitados)

        # 2. FILTRADO DEL GRAFO SEGÚN EL NIVEL
        nodos_filtrados, aristas_filtradas = self._filtrar_grafo_por_nivel(nodos, aristas, tipo_entidad_inicial, id_entidad_inicial, nivel)

        # 3. ENRIQUECIMIENTO DE DATOS Y FORMATEO FINAL
        self._enriquecer_datos_nodos(nodos_filtrados)
        
        resumen = self._generar_resumen(nodos_filtrados, aristas_filtradas, tipo_entidad_inicial, id_entidad_inicial)
        diagrama = self._generar_diagrama(nodos_filtrados, aristas_filtradas)

        return {'resumen': resumen, 'diagrama': diagrama}

    # --- MÉTODOS AUXILIARES ---

    def _agregar_nodo(self, nodos, tipo, id, data=None, es_generico=False):
        """Agrega un nodo a la colección si no existe."""
        if (tipo, id) not in nodos:
            nodos[(tipo, id)] = {'data': data, 'es_generico': es_generico}
    
    def _agregar_arista(self, aristas, tipo_origen, id_origen, tipo_destino, id_destino, cantidad):
        """Agrega una arista a la colección, asegurando que la cantidad sea numérica."""
        # Si la cantidad es None o una cadena vacía, usar 0.
        cantidad_numerica = cantidad if cantidad is not None and cantidad != '' else 0
        aristas.add(((tipo_origen, id_origen), (tipo_destino, id_destino), cantidad_numerica))

    def _agregar_nodo_y_arista(self, nodos, aristas, tipo_origen, id_origen, tipo_destino, id_destino, cantidad, cola, visitados):
        """Función helper para añadir nodos y aristas, y actualizar la cola de BFS."""
        self._agregar_nodo(nodos, tipo_origen, id_origen)
        self._agregar_nodo(nodos, tipo_destino, id_destino)
        # La arista va del origen (atrás) al destino (adelante)
        self._agregar_arista(aristas, tipo_origen, id_origen, tipo_destino, id_destino, cantidad)
        
        if (tipo_origen, id_origen) not in visitados:
            cola.append((tipo_origen, id_origen))
            visitados.add((tipo_origen, id_origen))
        if (tipo_destino, id_destino) not in visitados:
            cola.append((tipo_destino, id_destino))
            visitados.add((tipo_destino, id_destino))

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
        realizando una trazabilidad completa bidireccional.
        """
        # Se debe usar los nodos del diagrama, no las aristas, para asegurar que todos los puntos finales se incluyan.
        diagrama = self.obtener_trazabilidad_unificada(tipo_entidad_inicial, id_entidad_inicial, 'completo')['diagrama']
        nodos = diagrama.get('nodes', [])
        
        nodos_afectados = set()
        for nodo in nodos:
            # `rsplit` es más seguro si el tipo de entidad pudiera contener guiones bajos.
            tipo, id_entidad = nodo['id'].rsplit('_', 1)
            nodos_afectados.add((tipo, id_entidad))
        
        # El nodo inicial ya está garantizado por la lógica de `obtener_trazabilidad_unificada`,
        # por lo que no es necesario añadirlo explícitamente aquí.

        # Formatear para la salida esperada por el sistema de alertas
        resultado_formateado = []
        for tipo, id_str in nodos_afectados:
            # No intentar convertir IDs de nodos genéricos/manuales
            if 'generico' in id_str or 'manual' in id_str:
                continue
            
            # Intentar convertir a int para tipos de entidad que usan IDs numéricos
            if tipo in ['pedido', 'orden_produccion', 'lote_producto', 'orden_compra']:
                try:
                    id_entidad = int(id_str)
                except (ValueError, TypeError):
                    # Si falla la conversión, es un dato inconsistente, saltar
                    continue
            else:
                # Para otros tipos (como lote_insumo con UUID), mantener el string
                id_entidad = id_str
            
            resultado_formateado.append({'tipo_entidad': tipo, 'id_entidad': id_entidad})

        return resultado_formateado


    @classmethod
    def get_table_name(cls):
        return None

    @classmethod
    def get_id_column(cls):
        return None