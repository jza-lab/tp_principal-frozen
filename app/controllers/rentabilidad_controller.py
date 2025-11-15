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
            
            # 1. Calcular margen de ganancia
            margen_info = self._calcular_margen_ganancia(producto_id)
            
            # 2. Calcular volumen de ventas (total histórico de unidades)
            items_result = self.pedido_item_model.find_all({'producto_id': producto_id})
            volumen_ventas = 0
            facturacion_total = 0
            
            if items_result.get('success') and items_result.get('data'):
                for item in items_result['data']:
                    volumen_ventas += item.get('cantidad', 0)
                    # Asumimos que el precio está en el producto, para la facturación total
                    facturacion_total += item.get('cantidad', 0) * producto.get('precio_unitario', 0)

            datos_matriz.append({
                'id': producto_id,
                'nombre': producto.get('nombre'),
                'volumen_ventas': volumen_ventas,
                'margen_ganancia': margen_info['margen_porcentual'],
                'facturacion_total': facturacion_total
            })

        return self.success_response(data=datos_matriz)


    def _calcular_costo_producto(self, producto_id: int) -> float:
        """
        Calcula el costo total de un producto basado en los insumos de su receta.
        Devuelve el costo total o 0.0 si no se puede calcular.
        """
        try:
            receta_result = self.receta_model.find_all({'producto_id': producto_id, 'activa': True})
            if not receta_result.get('success') or not receta_result.get('data'):
                return 0.0
            receta = receta_result['data'][0]
            
            ingredientes_result = self.receta_model.get_ingredientes(receta['id'])
            if not ingredientes_result.get('success'):
                return 0.0

            costo_total = 0.0
            for ingrediente in ingredientes_result.get('data', []):
                insumo_id = ingrediente.get('id_insumo')
                if not insumo_id: continue

                insumo_result = self.insumo_model.find_by_id(insumo_id)
                if insumo_result.get('success') and insumo_result.get('data'):
                    costo_insumo = insumo_result['data'].get('precio_unitario', 0.0)
                    cantidad = ingrediente.get('cantidad', 0.0)
                    costo_total += (costo_insumo or 0.0) * (cantidad or 0.0)
            
            return costo_total
        except Exception:
            return 0.0

    def _calcular_margen_ganancia(self, producto_id: int) -> Dict:
        """
        Calcula el margen de ganancia para un único producto.
        """
        try:
            producto_result = self.producto_model.find_by_id(producto_id)
            if not producto_result.get('success') or not producto_result.get('data'):
                return {'margen_porcentual': 0.0, 'margen_absoluto': 0.0}

            producto = producto_result['data']
            precio_venta = producto.get('precio_unitario', 0.0) or 0.0
            costo_producto = self._calcular_costo_producto(producto_id)

            if precio_venta == 0:
                return {'margen_porcentual': 0.0, 'margen_absoluto': -costo_producto}

            margen_absoluto = precio_venta - costo_producto
            margen_porcentual = (margen_absoluto / precio_venta) * 100
            
            return {
                'margen_porcentual': round(margen_porcentual, 2),
                'margen_absoluto': round(margen_absoluto, 2)
            }
        except Exception:
            return {'margen_porcentual': 0.0, 'margen_absoluto': 0.0}


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

        return self.success_response(data={
            'nombre_producto': producto_nombre,
            'historial_ventas': sorted(historial_ventas, key=lambda x: x['fecha'], reverse=True),
            'historial_precios': historial_precios_ordenado,
            'clientes_principales': clientes_principales
        })

