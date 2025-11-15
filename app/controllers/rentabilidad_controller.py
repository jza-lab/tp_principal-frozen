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

    def obtener_datos_matriz_rentabilidad(self) -> tuple:
        """
        Orquesta el cálculo de métricas para todos los productos
        y devuelve los datos necesarios para el gráfico de burbujas.
        """
        productos_result = self.producto_model.find_all({'activo': True})
        if not productos_result.get('success'):
            return self.error_response("Error al obtener productos.", 500)

        datos_matriz = []
        for producto in productos_result.get('data', []):
            producto_id = producto['id']
            
            # 1. Calcular margen de ganancia y costos
            margen_info = self._calcular_margen_ganancia(producto_id)
            
            # 2. Calcular volumen de ventas (total histórico de unidades)
            items_result = self.pedido_item_model.find_all({'producto_id': producto_id})
            volumen_ventas = 0
            facturacion_total = 0
            
            if items_result.get('success') and items_result.get('data'):
                for item in items_result['data']:
                    volumen_ventas += item.get('cantidad', 0)
                    facturacion_total += item.get('cantidad', 0) * (producto.get('precio_unitario', 0) or 0)

            # 3. Ensamblar los datos para la respuesta
            ganancia_bruta = margen_info['margen_absoluto'] * volumen_ventas
            costo_total_ventas = margen_info['costos']['costo_total'] * volumen_ventas

            datos_matriz.append({
                'id': producto_id,
                'nombre': producto.get('nombre'),
                'volumen_ventas': volumen_ventas,
                'margen_ganancia': margen_info['margen_porcentual'],
                'ganancia_bruta': round(ganancia_bruta, 2),
                'facturacion_total': round(facturacion_total, 2),
                'costo_total': round(costo_total_ventas, 2)
            })

        return self.success_response(data=datos_matriz)


    def _calcular_costo_producto(self, producto_id: int) -> Dict:
        """
        Calcula el costo desglosado de un producto (materia prima, mano de obra, total).
        Devuelve un diccionario con los costos o un diccionario con ceros si falla.
        """
        default_cost = {'costo_materia_prima': 0.0, 'costo_mano_obra': 0.0, 'costo_total': 0.0}
        try:
            # Obtener el producto para el 'porcentaje_extra'
            producto_result = self.producto_model.find_by_id(producto_id)
            if not producto_result.get('success') or not producto_result.get('data'):
                return default_cost
            producto = producto_result['data']
            porcentaje_mano_obra = (producto.get('porcentaje_mano_obra', 0.0) or 0.0) / 100

            # Calcular costo de materia prima (lógica existente)
            costo_materia_prima = 0.0
            receta_result = self.receta_model.find_all({'producto_id': producto_id, 'activa': True})
            if receta_result.get('success') and receta_result.get('data'):
                receta = receta_result['data'][0]
                ingredientes_result = self.receta_model.get_ingredientes(receta['id'])
                if ingredientes_result.get('success'):
                    for ingrediente in ingredientes_result.get('data', []):
                        insumo_id = ingrediente.get('id_insumo')
                        if not insumo_id: continue

                        insumo_result = self.insumo_model.find_by_id(insumo_id)
                        if insumo_result.get('success') and insumo_result.get('data'):
                            costo_insumo = insumo_result['data'].get('precio_unitario', 0.0)
                            cantidad = ingrediente.get('cantidad', 0.0)
                            costo_materia_prima += (costo_insumo or 0.0) * (cantidad or 0.0)
            
            # Calcular costo de mano de obra y total
            costo_mano_obra = costo_materia_prima * porcentaje_mano_obra
            costo_total = costo_materia_prima + costo_mano_obra
            
            return {
                'costo_materia_prima': round(costo_materia_prima, 2),
                'costo_mano_obra': round(costo_mano_obra, 2),
                'costo_total': round(costo_total, 2)
            }
        except Exception:
            return default_cost

    def _calcular_margen_ganancia(self, producto_id: int) -> Dict:
        """
        Calcula el margen de ganancia y obtiene el desglose de costos para un único producto.
        """
        default_margen = {'margen_porcentual': 0.0, 'margen_absoluto': 0.0, 'costos': {'costo_materia_prima': 0.0, 'costo_mano_obra': 0.0, 'costo_total': 0.0}}
        try:
            producto_result = self.producto_model.find_by_id(producto_id)
            if not producto_result.get('success') or not producto_result.get('data'):
                return default_margen

            producto = producto_result['data']
            precio_venta = producto.get('precio_unitario', 0.0) or 0.0
            
            costos_info = self._calcular_costo_producto(producto_id)
            costo_total = costos_info['costo_total']

            if precio_venta == 0:
                return {
                    'margen_porcentual': 0.0, 
                    'margen_absoluto': -costo_total,
                    'costos': costos_info
                }

            margen_absoluto = precio_venta - costo_total
            margen_porcentual = (margen_absoluto / precio_venta) * 100 if precio_venta > 0 else 0
            
            return {
                'margen_porcentual': round(margen_porcentual, 2),
                'margen_absoluto': round(margen_absoluto, 2),
                'costos': costos_info
            }
        except Exception:
            return default_margen


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
        # 1. Obtener el nombre del producto
        producto_result = self.producto_model.find_by_id(producto_id)
        if not producto_result.get('success') or not producto_result.get('data'):
            return self.error_response("Producto no encontrado", 404)
        producto_nombre = producto_result['data'].get('nombre', 'Producto Desconocido')

        # 2. Obtener todos los items de venta para ese producto, uniéndolos con el producto y el pedido.
        try:
            items_result = self.producto_model.db.table('pedido_items').select(
                'cantidad, producto:productos!inner(precio_unitario), pedido:pedidos!pedido_items_pedido_id_fkey!inner(fecha_solicitud, nombre_cliente)'
            ).eq('producto_id', producto_id).execute()

            if not items_result.data:
                return self.success_response(data={
                    'nombre_producto': producto_nombre,
                    'historial_ventas': [], 'historial_precios': [], 'clientes_principales': []
                })
        except Exception as e:
            logger.error(f"Error al consultar detalles para producto ID {producto_id}: {e}", exc_info=True)
            return self.error_response("Error al obtener detalles del producto.", 500)

        historial_ventas, historial_precios, clientes = [], {}, {}

        for item in items_result.data:
            if not item.get('producto') or not item.get('pedido'):
                continue
            
            cantidad = item.get('cantidad', 0)
            precio_unitario = item['producto'].get('precio_unitario', 0.0) or 0.0
            subtotal = cantidad * precio_unitario
            
            fecha = item['pedido'].get('fecha_solicitud')
            cliente_nombre = item['pedido'].get('nombre_cliente', 'N/A')

            # Poblar historial de ventas
            historial_ventas.append({'fecha': fecha, 'cantidad': cantidad, 'cliente': cliente_nombre, 'subtotal': subtotal})

            # Poblar historial de precios (evita duplicados por fecha)
            if fecha:
                fecha_corta = fecha.split('T')[0]
                if fecha_corta not in historial_precios:
                     historial_precios[fecha_corta] = round(precio_unitario, 2)

            # Agregar datos de clientes
            if cliente_nombre not in clientes:
                clientes[cliente_nombre] = {'facturacion': 0, 'unidades': 0}
            clientes[cliente_nombre]['facturacion'] += subtotal
            clientes[cliente_nombre]['unidades'] += cantidad

        # Ordenar resultados
        clientes_principales = sorted(clientes.items(), key=lambda x: x[1]['facturacion'], reverse=True)
        historial_precios_ordenado = sorted(historial_precios.items(), key=lambda x: x[0])

        # 3. Obtener el desglose de costos
        costos_info = self._calcular_costo_producto(producto_id)

        return self.success_response(data={
            'nombre_producto': producto_nombre,
            'historial_ventas': sorted(historial_ventas, key=lambda x: x['fecha'], reverse=True),
            'historial_precios': historial_precios_ordenado,
            'clientes_principales': clientes_principales,
            'costos': costos_info
        })

