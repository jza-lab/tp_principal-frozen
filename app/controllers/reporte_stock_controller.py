from app.models.insumo import InsumoModel
from app.models.inventario import InventarioModel
from app.models.producto import ProductoModel
from app.models.lote_producto import LoteProductoModel
from app.models.pedido import PedidoModel
from datetime import datetime, timedelta

class ReporteStockController:
    def __init__(self):
        self.insumo_model = InsumoModel()
        self.inventario_model = InventarioModel()
        self.producto_model = ProductoModel()
        self.lote_producto_model = LoteProductoModel()
        self.pedido_model = PedidoModel()

    # --- Métodos para Insumos ---

    def obtener_composicion_stock_insumos(self):
        """
        Calcula la cantidad total de stock de insumos y la agrupa por categoría.
        """
        try:
            response = self.inventario_model.obtener_stock_consolidado()
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudo obtener el stock consolidado de insumos.'}

            insumos = response.get('data', [])
            if not insumos:
                return {'success': True, 'data': {}}

            composicion = {}
            for insumo in insumos:
                categoria = insumo.get('categoria', 'Sin Categoría')
                cantidad = float(insumo.get('stock_actual', 0))
                if categoria in composicion:
                    composicion[categoria] += cantidad
                else:
                    composicion[categoria] = cantidad
            
            return {'success': True, 'data': composicion}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # --- Nuevos Métodos de Análisis de Stock de Productos ---

    def obtener_valor_stock_por_categoria_producto(self):
        """
        Calcula el valor monetario total del stock para cada categoría de producto terminado.
        """
        try:
            # 1. Obtener el stock valorizado total por producto (nombre, valor_total_stock)
            productos_valorizados = self.lote_producto_model.get_stock_valorizado()
            if not productos_valorizados:
                return {'success': True, 'data': {}}

            # 2. Obtener las categorías de todos los productos
            productos_response = self.producto_model.find_all(select_columns=['nombre', 'categoria'])
            if not productos_response.get('success'):
                return productos_response
            
            categoria_map = {p['nombre']: p.get('categoria', 'Sin Categoría') for p in productos_response.get('data', [])}

            # 3. Agrupar por categoría
            valor_por_categoria = {}
            for producto in productos_valorizados:
                nombre = producto['nombre']
                categoria = categoria_map.get(nombre, 'Sin Categoría')
                valor = float(producto['valor_total_stock'])

                if categoria in valor_por_categoria:
                    valor_por_categoria[categoria] += valor
                else:
                    valor_por_categoria[categoria] = valor
            
            # Ordenar de mayor a menor valor
            valor_ordenado = dict(sorted(valor_por_categoria.items(), key=lambda item: item[1], reverse=True))

            return {'success': True, 'data': valor_ordenado}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_distribucion_stock_por_estado_producto(self):
        """
        Calcula la cantidad de stock de productos terminados agrupada por su estado.
        """
        try:
            response = self.lote_producto_model.obtener_stock_por_estado()
            if not response.get('success'):
                return response
            
            return {'success': True, 'data': response.get('data', {})}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_valor_stock_insumos(self, top_n=10):
        """
        Calcula el valor total del stock para cada insumo y devuelve los N más valiosos.
        """
        try:
            response = self.inventario_model.obtener_stock_consolidado()
            if not response.get('success'):
                return {'success': False, 'error': 'No se pudo obtener el stock consolidado de insumos.'}

            insumos = response.get('data', [])
            if not insumos:
                return {'success': True, 'data': {}}

            valores = []
            for insumo in insumos:
                nombre = insumo.get('nombre', 'Desconocido')
                cantidad = float(insumo.get('stock_actual', 0))
                precio = float(insumo.get('precio_unitario', 0))
                valor_total = cantidad * precio
                if valor_total > 0:
                    valores.append({'nombre': nombre, 'valor': valor_total})
            
            valores_ordenados = sorted(valores, key=lambda x: x['valor'], reverse=True)
            top_n_data = {item['nombre']: round(item['valor'], 2) for item in valores_ordenados[:top_n]}

            return {'success': True, 'data': top_n_data}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_insumos_stock_critico(self):
        """
        Obtiene los insumos cuyo stock actual es menor o igual a su stock mínimo definido.
        """
        try:
            response = self.inventario_model.obtener_stock_consolidado()
            if not response.get('success'):
                return response
            
            insumos = response.get('data', [])
            insumos_criticos = []
            for insumo in insumos:
                stock_actual = float(insumo.get('stock_actual', 0))
                stock_minimo = float(insumo.get('stock_min', 0))
                if stock_minimo > 0 and stock_actual <= stock_minimo:
                    insumos_criticos.append({
                        'nombre': insumo.get('nombre'),
                        'stock_actual': stock_actual,
                        'stock_min': stock_minimo,
                        'unidad_medida': insumo.get('unidad_medida')
                    })
            
            return {'success': True, 'data': insumos_criticos}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_lotes_insumos_a_vencer(self, dias_horizonte=30):
        """
        Obtiene los lotes de insumos que vencerán en los próximos X días.
        """
        try:
            response = self.inventario_model.obtener_por_vencimiento(dias_horizonte)
            if not response.get('success'):
                return response
            
            return {'success': True, 'data': response.get('data', [])}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # --- Métodos para Productos ---

    def obtener_composicion_stock_productos(self):
        """
        Calcula la cantidad total de stock de productos terminados y la agrupa por nombre de producto.
        """
        try:
            response = self.lote_producto_model.obtener_composicion_inventario()
            if not response.get('success'):
                return response
            
            # La respuesta del modelo ya viene procesada
            # La convertimos al formato {nombre: cantidad} que esperan los gráficos
            data = response.get('data', [])
            composicion = {item['nombre']: item['cantidad'] for item in data}
            
            return {'success': True, 'data': composicion}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_valor_stock_productos(self, top_n=10):
        """
        Calcula el valor total del stock para cada producto terminado y devuelve los N más valiosos.
        """
        try:
            # 1. Obtener el stock total por producto
            stock_response = self.lote_producto_model.obtener_composicion_inventario()
            if not stock_response.get('success'):
                return stock_response
            
            stock_map = {item['nombre']: item['cantidad'] for item in stock_response.get('data', [])}

            # 2. Obtener los precios de todos los productos
            productos_response = self.producto_model.find_all()
            if not productos_response.get('success'):
                return productos_response
            
            productos = productos_response.get('data', [])
            
            # 3. Calcular el valor total
            valores = []
            for producto in productos:
                nombre = producto.get('nombre')
                if nombre in stock_map:
                    cantidad = float(stock_map[nombre])
                    precio = float(producto.get('precio_unitario', 0))
                    valor_total = cantidad * precio
                    if valor_total > 0:
                        valores.append({'nombre': nombre, 'valor': valor_total})

            # 4. Ordenar y devolver el top N
            valores_ordenados = sorted(valores, key=lambda x: x['valor'], reverse=True)
            top_n_data = {item['nombre']: round(item['valor'], 2) for item in valores_ordenados[:top_n]}

            return {'success': True, 'data': top_n_data}

        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def obtener_productos_bajo_stock(self):
        """
        Obtiene los productos terminados cuyo stock total es menor o igual a su stock mínimo definido.
        """
        try:
            stock_response = self.lote_producto_model.obtener_composicion_inventario()
            if not stock_response.get('success'):
                return stock_response
            stock_map = {item['nombre']: item['cantidad'] for item in stock_response.get('data', [])}

            productos_response = self.producto_model.find_all()
            if not productos_response.get('success'):
                return productos_response
            
            productos = productos_response.get('data', [])
            
            productos_bajos = []
            for producto in productos:
                nombre = producto.get('nombre')
                stock_minimo = float(producto.get('stock_minimo', 0))
                
                # Asegurarse de que el producto esté en el mapa de stock, incluso si es 0
                stock_actual = float(stock_map.get(nombre, 0))

                if stock_minimo > 0 and stock_actual <= stock_minimo:
                    productos_bajos.append({
                        'nombre': nombre,
                        'stock_actual': stock_actual,
                        'stock_minimo': stock_minimo,
                        'unidad_medida': producto.get('unidad_medida')
                    })
            
            return {'success': True, 'data': productos_bajos}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def obtener_lotes_productos_a_vencer(self, dias_horizonte=30):
        """
        Obtiene los lotes de productos terminados que vencerán en los próximos X días.
        """
        try:
            response = self.lote_producto_model.find_por_vencimiento(dias_horizonte)
            if not response.get('success'):
                return response
            
            return {'success': True, 'data': response.get('data', [])}

        except Exception as e:
            return {'success': False, 'error': str(e)}
