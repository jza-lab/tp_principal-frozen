from datetime import datetime, timedelta
import logging
from app.controllers.base_controller import BaseController
from app.models.producto import ProductoModel
from app.models.receta import RecetaModel
from app.models.pedido import PedidoModel, PedidoItemModel
from app.models.insumo import InsumoModel
from typing import Dict, List

logger = logging.getLogger(__name__)

class RentabilidadController(BaseController):
    """
    Controlador para la lógica de negocio del análisis de rentabilidad.
    """

    def __init__(self):
        super().__init__()
        self.producto_model = ProductoModel()
        self.receta_model = RecetaModel()
        self.pedido_model = PedidoModel()
        self.insumo_model = InsumoModel()
        self.pedido_item_model = PedidoItemModel()

    def obtener_datos_matriz_rentabilidad(self, fecha_inicio: str = None, fecha_fin: str = None) -> tuple:
        """
        Orquesta el cálculo de métricas para todos los productos, con un rango de fechas opcional.
        """
        # 1. Obtener todos los productos activos y sus costos de una vez.
        productos_result = self.producto_model.find_all({'activo': True})
        if not productos_result.get('success'):
            return self.error_response("Error al obtener productos.", 500)
        
        productos_data = productos_result.get('data', [])
        productos_con_costo = {p['id']: self._calcular_margen_ganancia(p) for p in productos_data}

        # 2. Obtener los IDs de los pedidos dentro del rango de fechas.
        pedidos_en_rango_ids = None
        if fecha_inicio and fecha_fin:
            try:
                pedidos_query = self.pedido_model.db.table('pedidos').select('id').gte('fecha_solicitud', fecha_inicio).lte('fecha_solicitud', fecha_fin)
                pedidos_result = pedidos_query.execute()
                if hasattr(pedidos_result, 'data'):
                    pedidos_en_rango_ids = [p['id'] for p in pedidos_result.data]
                else:
                    pedidos_en_rango_ids = []
            except Exception as e:
                logger.error(f"Error al obtener pedidos en rango de fechas: {e}", exc_info=True)
                return self.error_response("Error al filtrar pedidos por fecha.", 500)

        # 3. Calcular ventas para cada producto.
        datos_matriz = []
        for producto_id, margen_info in productos_con_costo.items():
            producto_nombre = margen_info['nombre']
            
            items_query = self.pedido_item_model.db.table('pedido_items').select('cantidad').eq('producto_id', producto_id)
            if pedidos_en_rango_ids is not None:
                if not pedidos_en_rango_ids:
                    items_result = None # No hay pedidos, no hay ventas
                else:
                    items_result = items_query.in_('pedido_id', pedidos_en_rango_ids).execute()
            else: # Sin filtro de fecha, obtener todo
                items_result = items_query.execute()

            volumen_ventas = 0
            if items_result and hasattr(items_result, 'data'):
                volumen_ventas = sum(item.get('cantidad', 0) for item in items_result.data)
            
            precio_unitario = margen_info.get('precio_venta', 0)
            facturacion_total = volumen_ventas * precio_unitario
            ganancia_bruta = margen_info['margen_absoluto'] * volumen_ventas
            costo_total_ventas = margen_info['costos']['costo_total'] * volumen_ventas

            datos_matriz.append({
                'id': producto_id,
                'nombre': producto_nombre,
                'volumen_ventas': volumen_ventas,
                'margen_ganancia': margen_info['margen_porcentual'],
                'ganancia_bruta': round(ganancia_bruta, 2),
                'facturacion_total': round(facturacion_total, 2),
                'costo_total': round(costo_total_ventas, 2),
                'costos_unitarios': margen_info['costos']
            })

        # 4. Calcular promedios y devolver respuesta.
        productos_con_ventas = [p for p in datos_matriz if p['volumen_ventas'] > 0]
        if not productos_con_ventas:
            return self.success_response(data={'productos': [], 'promedios': {'volumen_ventas': 0, 'margen_ganancia': 0}})

        total_productos = len(productos_con_ventas)
        volumen_ventas_total = sum(p['volumen_ventas'] for p in productos_con_ventas)
        margen_ganancia_total = sum(p['margen_ganancia'] for p in productos_con_ventas)
        
        volumen_promedio = volumen_ventas_total / total_productos
        margen_promedio = margen_ganancia_total / total_productos

        respuesta = {
            'productos': datos_matriz,
            'promedios': {
                'volumen_ventas': round(volumen_promedio, 2),
                'margen_ganancia': round(margen_promedio, 2)
            }
        }
        return self.success_response(data=respuesta)

    def obtener_evolucion_producto(self, producto_id: int) -> tuple:
        """
        Devuelve la evolución de ventas y margen para un producto en los últimos 12 meses.
        """
        # 1. Obtener datos del producto y calcular su margen unitario
        producto_result = self.producto_model.find_by_id(producto_id)
        if not producto_result.get('success') or not producto_result.get('data'):
            return self.error_response("Producto no encontrado", 404)
        
        producto_data = producto_result.get('data')
        margen_info = self._calcular_margen_ganancia(producto_data)
        precio_venta_unitario = margen_info.get('precio_venta', 0)
        margen_absoluto_unitario = margen_info.get('margen_absoluto', 0)

        # 2. Obtener ventas del último año
        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=365)
        
        try:
            # Primero, obtenemos los IDs de los pedidos en el rango de fechas
            pedidos_resp = self.pedido_model.db.table('pedidos').select('id').gte(
                'fecha_solicitud', fecha_inicio.isoformat()
            ).lte('fecha_solicitud', fecha_fin.isoformat()).execute()
            
            if not hasattr(pedidos_resp, 'data'):
                return self.success_response(data=[]) # No hay pedidos, no hay evolución
            
            pedido_ids_en_rango = [p['id'] for p in pedidos_resp.data]
            if not pedido_ids_en_rango:
                return self.success_response(data=[])

            # Luego, obtenemos los items de este producto en esos pedidos
            items_result = self.pedido_item_model.db.table('pedido_items').select(
                'cantidad, pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud)'
            ).eq('producto_id', producto_id).in_('pedido_id', pedido_ids_en_rango).execute()
            
        except Exception as e:
            logger.error(f"Error al obtener evolucion para producto ID {producto_id}: {e}", exc_info=True)
            return self.error_response("Error al obtener evolucion del producto.", 500)

        # 3. Agregar datos por mes
        from collections import defaultdict
        ventas_por_mes = defaultdict(lambda: {'unidades': 0, 'facturacion': 0, 'ganancia': 0})
        
        if hasattr(items_result, 'data'):
            for item in items_result.data:
                if not item.get('pedido') or not item['pedido'].get('fecha_solicitud'):
                    continue
                
                fecha_str = item['pedido']['fecha_solicitud']
                mes_key = datetime.fromisoformat(fecha_str).strftime('%Y-%m')
                cantidad = item.get('cantidad', 0)
                
                ventas_por_mes[mes_key]['unidades'] += cantidad
                ventas_por_mes[mes_key]['facturacion'] += cantidad * precio_venta_unitario
                ventas_por_mes[mes_key]['ganancia'] += cantidad * margen_absoluto_unitario

        # 4. Formatear la respuesta, asegurando que existan los 12 meses
        evolucion = []
        for i in range(12):
            mes_actual = fecha_fin - timedelta(days=i * 30)
            mes_key = mes_actual.strftime('%Y-%m')
            
            datos_mes = ventas_por_mes.get(mes_key, {'unidades': 0, 'facturacion': 0, 'ganancia': 0})
            
            margen_porcentual = (datos_mes['ganancia'] / datos_mes['facturacion']) * 100 if datos_mes['facturacion'] > 0 else 0
            evolucion.append({
                "mes": mes_key,
                "unidades_vendidas": datos_mes['unidades'],
                "margen_ganancia_porcentual": round(margen_porcentual, 2)
            })

        # Ordenar por mes de forma ascendente
        evolucion.sort(key=lambda x: x['mes'])
        return self.success_response(data=evolucion)

    def _calcular_costo_producto(self, producto: Dict) -> Dict:
        """
        Calcula el costo desglosado de un producto (materia prima, mano de obra, total).
        Recibe el diccionario del producto para evitar consultas repetidas.
        """
        default_cost = {'costo_materia_prima': 0.0, 'costo_mano_obra': 0.0, 'costo_total': 0.0}
        if not producto:
            return default_cost
            
        try:
            producto_id = producto['id']
            porcentaje_mano_obra = (producto.get('porcentaje_mano_obra', 0.0) or 0.0) / 100

            costo_materia_prima = 0.0
            receta_result = self.receta_model.find_all({'producto_id': producto_id, 'activa': True}, limit=1)
            
            if receta_result.get('success') and receta_result.get('data'):
                receta = receta_result.get('data', [])[0]
                ingredientes_result = self.receta_model.get_ingredientes(receta['id'])
                if ingredientes_result.get('success'):
                    for ingrediente in ingredientes_result.get('data', []):
                        insumo_id = ingrediente.get('id_insumo')
                        if not insumo_id: continue
                        
                        insumo_result = self.insumo_model.find_by_id(insumo_id)
                        if insumo_result.get('success') and insumo_result.get('data'):
                            costo_insumo = insumo_result.get('data', {}).get('precio_unitario', 0.0)
                            cantidad = ingrediente.get('cantidad', 0.0)
                            costo_materia_prima += (costo_insumo or 0.0) * (cantidad or 0.0)
            
            costo_mano_obra = costo_materia_prima * porcentaje_mano_obra
            costo_total = costo_materia_prima + costo_mano_obra
            
            return {
                'costo_materia_prima': round(costo_materia_prima, 2),
                'costo_mano_obra': round(costo_mano_obra, 2),
                'costo_total': round(costo_total, 2)
            }
        except Exception as e:
            logger.error(f"Error al calcular costo para producto ID {producto.get('id')}: {e}", exc_info=True)
            return default_cost

    def _calcular_margen_ganancia(self, producto: Dict) -> Dict:
        """
        Calcula el margen de ganancia a partir de un diccionario de producto.
        """
        default_margen = {'nombre': 'N/A', 'margen_porcentual': 0.0, 'margen_absoluto': 0.0, 'costos': {'costo_materia_prima': 0.0, 'costo_mano_obra': 0.0, 'costo_total': 0.0}, 'precio_venta': 0}
        if not producto:
            return default_margen

        try:
            precio_venta = producto.get('precio_unitario', 0.0) or 0.0
            costos_info = self._calcular_costo_producto(producto)
            costo_total = costos_info['costo_total']
            
            margen_absoluto = precio_venta - costo_total
            margen_porcentual = (margen_absoluto / precio_venta) * 100 if precio_venta > 0 else 0
            
            return {
                'nombre': producto.get('nombre'),
                'margen_porcentual': round(margen_porcentual, 2),
                'margen_absoluto': round(margen_absoluto, 2),
                'costos': costos_info,
                'precio_venta': precio_venta
            }
        except Exception as e:
            logger.error(f"Error al calcular margen para producto ID {producto.get('id')}: {e}", exc_info=True)
            return {**default_margen, 'nombre': producto.get('nombre', 'N/A')}

    def calcular_crecimiento_ventas(self, periodo: str, metrica: str) -> tuple:
        """
        Calcula el crecimiento en ventas comparando dos períodos.
        """
        hoy = datetime.now()
        if periodo == 'mes':
            fecha_fin_actual = hoy
            fecha_inicio_actual = hoy - timedelta(days=30)
            fecha_fin_anterior = fecha_inicio_actual - timedelta(days=1)
            fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=30)
        elif periodo == 'trimestre':
            fecha_fin_actual = hoy
            fecha_inicio_actual = hoy - timedelta(days=90)
            fecha_fin_anterior = fecha_inicio_actual - timedelta(days=1)
            fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=90)
        else: # año
            fecha_fin_actual = hoy
            fecha_inicio_actual = hoy - timedelta(days=365)
            fecha_fin_anterior = fecha_inicio_actual - timedelta(days=1)
            fecha_inicio_anterior = fecha_fin_anterior - timedelta(days=365)

        total_actual = self._obtener_total_ventas_periodo(fecha_inicio_actual, fecha_fin_actual, metrica)
        total_anterior = self._obtener_total_ventas_periodo(fecha_inicio_anterior, fecha_fin_anterior, metrica)

        if total_anterior == 0:
            crecimiento = 100.0 if total_actual > 0 else 0.0
        else:
            crecimiento = ((total_actual - total_anterior) / total_anterior) * 100

        return self.success_response(data={'crecimiento': round(crecimiento, 2), 'periodo_actual': total_actual, 'periodo_anterior': total_anterior})

    def _obtener_total_ventas_periodo(self, fecha_inicio: datetime, fecha_fin: datetime, metrica: str) -> float:
        """Función auxiliar para obtener el total de ventas en un rango de fechas."""
        pedidos_result = self.pedido_model.get_all_with_items(filtros={
            'fecha_desde': fecha_inicio.strftime('%Y-%m-%d'),
            'fecha_hasta': fecha_fin.strftime('%Y-%m-%d')
        })
        
        total = 0.0
        if pedidos_result.get('success') and pedidos_result.get('data'):
            for pedido in pedidos_result['data']:
                if metrica == 'facturacion':
                    total += pedido.get('total', 0.0) or 0.0
                else: # unidades
                    for item in pedido.get('pedido_items', []):
                        total += item.get('cantidad', 0)
        return total

    def obtener_detalles_producto(self, producto_id: int) -> tuple:
        """
        Devuelve detalles de un producto: historial de ventas, historial de precios (inferido) y clientes principales.
        """
        producto_result = self.producto_model.find_by_id(producto_id)
        if not producto_result.get('success') or not producto_result.get('data'):
            return self.error_response("Producto no encontrado", 404)
        
        producto_data = producto_result['data']
        producto_nombre = producto_data.get('nombre', 'Producto Desconocido')

        try:
            items_result = self.producto_model.db.table('pedido_items').select(
                'cantidad, pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud, nombre_cliente)'
            ).eq('producto_id', producto_id).execute()

            if not items_result.data:
                return self.success_response(data={
                    'nombre_producto': producto_nombre,
                    'historial_ventas': [], 'historial_precios': [], 'clientes_principales': [],
                    'costos': self._calcular_costo_producto(producto_data) # Devuelve costos incluso sin ventas
                })
        except Exception as e:
            logger.error(f"Error al consultar detalles para producto ID {producto_id}: {e}", exc_info=True)
            return self.error_response("Error al obtener detalles del producto.", 500)

        historial_ventas, historial_precios, clientes = [], {}, {}
        precio_unitario_actual = producto_data.get('precio_unitario', 0.0) or 0.0

        for item in items_result.data:
            if not item.get('pedido'):
                continue
            
            cantidad = item.get('cantidad', 0)
            subtotal = cantidad * precio_unitario_actual
            fecha = item['pedido'].get('fecha_solicitud')
            cliente_nombre = item['pedido'].get('nombre_cliente', 'N/A')

            historial_ventas.append({'fecha': fecha, 'cantidad': cantidad, 'cliente': cliente_nombre, 'subtotal': subtotal})
            
            if fecha:
                fecha_corta = fecha.split('T')[0]
                if fecha_corta not in historial_precios:
                     historial_precios[fecha_corta] = round(precio_unitario_actual, 2)

            if cliente_nombre not in clientes:
                clientes[cliente_nombre] = {'facturacion': 0, 'unidades': 0}
            clientes[cliente_nombre]['facturacion'] += subtotal
            clientes[cliente_nombre]['unidades'] += cantidad

        clientes_principales = sorted(clientes.items(), key=lambda x: x[1]['facturacion'], reverse=True)
        historial_precios_ordenado = sorted(historial_precios.items(), key=lambda x: x[0])
        costos_info = self._calcular_costo_producto(producto_data)

        return self.success_response(data={
            'nombre_producto': producto_nombre,
            'historial_ventas': sorted(historial_ventas, key=lambda x: x['fecha'], reverse=True),
            'historial_precios': historial_precios_ordenado,
            'clientes_principales': clientes_principales,
            'costos': costos_info
        })
