from app.controllers.base_controller import BaseController
from app.models.trazabilidad import TrazabilidadModel
from app.models.orden_produccion import OrdenProduccionModel
from app.models.reserva_insumo import ReservaInsumoModel
from app.models.inventario import InventarioModel
from app.models.lote_producto import LoteProductoModel
from app.models.pedido import PedidoModel
from app.models.cliente import ClienteModel
from app.models.proveedor import ProveedorModel
from app.models.reserva_producto import ReservaProductoModel

import logging

logger = logging.getLogger(__name__)

class TrazabilidadController(BaseController):
    def __init__(self):
        super().__init__()
        self.trazabilidad_model = TrazabilidadModel()
        self.orden_produccion_model = OrdenProduccionModel()
        self.reserva_insumo_model = ReservaInsumoModel()
        self.inventario_model = InventarioModel()
        self.lote_producto_model = LoteProductoModel()
        self.reserva_producto_model = ReservaProductoModel()
        self.pedido_model = PedidoModel()
        self.cliente_model = ClienteModel()
        self.proveedor_model = ProveedorModel()
    
    def get_trazabilidad_orden_produccion(self, orden_produccion_id):
        try:
            # 1. Obtener la orden de producción principal
            op_result = self.orden_produccion_model.get_one_enriched(orden_produccion_id)
            if not op_result.get('success'):
                return {'success': False, 'error': 'Orden de producción no encontrada'}
            
            orden_produccion_data = op_result['data']

            # 2. Trazabilidad Ascendente (Upstream)
            insumos_usados = []
            reservas_result = self.reserva_insumo_model.get_by_orden_produccion_id(orden_produccion_id)
            if reservas_result.get('success'):
                for reserva in reservas_result['data']:
                    lote_inventario = reserva.get('lote_inventario', {})
                    if lote_inventario:
                        proveedor_info = lote_inventario.get('proveedor') # Puede ser None
                        
                        proveedor_id = None
                        proveedor_nombre = 'Proveedor no asignado'
                        if proveedor_info:
                            proveedor_id = proveedor_info.get('id')
                            proveedor_nombre = proveedor_info.get('nombre', 'Proveedor sin nombre')

                        insumos_usados.append({
                            'id_lote_insumo': lote_inventario.get('id_lote'),
                            'lote_insumo': lote_inventario.get('numero_lote_proveedor', 'N/A'),
                            'nombre_insumo': lote_inventario.get('insumo',{}).get('nombre', 'N/A'),
                            'cantidad_usada': reserva.get('cantidad_reservada'),
                            'id_proveedor': proveedor_id,
                            'proveedor': proveedor_nombre
                        })

            # 3. Trazabilidad Descendente (Downstream) - LÓGICA CORREGIDA Y SIMPLIFICADA
            lotes_producidos = []
            pedidos_asociados = []
            pedidos_completos = {} # Usamos un dict para evitar duplicados y guardar info completa

            # Obtenemos los lotes producidos (esta parte estaba bien)
            from app.database import Database
            db = Database().client
            lotes_producidos_result = db.table('lotes_productos').select(
                'id_lote, numero_lote, cantidad_inicial'
            ).eq('orden_produccion_id', orden_produccion_id).execute()

            if lotes_producidos_result.data:
                for lote in lotes_producidos_result.data:
                    lotes_producidos.append({
                        'id': lote.get('id_lote'),
                        'numero_lote': lote.get('numero_lote'),
                        'cantidad_producida': lote.get('cantidad_inicial')
                    })

            # Obtenemos los pedidos asociados directamente desde pedido_items
            from app.database import Database
            db = Database().client
            items_result = db.table('pedido_items').select(
                'pedido:pedidos!pedido_items_pedido_id_fkey!inner(id, nombre_cliente, fecha_requerido)'
            ).eq('orden_produccion_id', orden_produccion_id).execute()
            
            if items_result.data:
                for item in items_result.data:
                    pedido_info = item.get('pedido')
                    if pedido_info and pedido_info.get('id') not in pedidos_completos:
                        pedidos_completos[pedido_info['id']] = pedido_info

            for _, pedido in pedidos_completos.items():
                pedidos_asociados.append({
                    'id': pedido.get('id'),
                    'codigo_pedido': f"PED-{pedido.get('id'):06d}",
                    'cliente': pedido.get('nombre_cliente', 'N/A'),
                    'fecha_entrega': pedido.get('fecha_requerido')
                })

            # 4. Obtener Órdenes de Compra asociadas
            ocs_asociadas_res = db.table('ordenes_compra').select(
                '*, '
                'proveedores:proveedor_id(id, nombre), '
                'orden_compra_items(*, insumos_catalogo:insumo_id(nombre))'
            ).eq('orden_produccion_id', orden_produccion_id).execute()
            
            ocs_asociadas = ocs_asociadas_res.data if ocs_asociadas_res.data else []
            resumen_ocs_asociadas = []
            if ocs_asociadas:
                for oc in ocs_asociadas:
                    items = []
                    if oc.get('orden_compra_items'):
                        for item in oc['orden_compra_items']:
                            items.append({
                                'nombre_insumo': item.get('insumos_catalogo', {}).get('nombre', 'N/A'),
                                'cantidad_solicitada': item.get('cantidad_solicitada')
                            })
                    
                    resumen_ocs_asociadas.append({
                        'id': oc.get('id'),
                        'codigo_oc': oc.get('codigo_oc'),
                        'proveedor_id': oc.get('proveedores', {}).get('id'),
                        'proveedor_nombre': oc.get('proveedores', {}).get('nombre', 'N/A'),
                        'estado': oc.get('estado'),
                        'fecha_estimada_entrega': oc.get('fecha_estimada_entrega'),
                        'fecha_real_entrega': oc.get('fecha_real_entrega'),
                        'items': items
                    })

            # 5. Estructurar la respuesta final
            response_data = {
                'resumen': {
                    'origen': {
                        'op': {
                            'codigo': orden_produccion_data.get('codigo'),
                            'producto': orden_produccion_data.get('producto_nombre'),
                            'cantidad_planificada': orden_produccion_data.get('cantidad_planificada'),
                            'fecha_inicio_planificada': orden_produccion_data.get('fecha_inicio_planificada')
                        },
                        'insumos': insumos_usados
                    },
                    'destino': {
                        'lotes': lotes_producidos,
                        'pedidos': pedidos_asociados
                    },
                    'ordenes_compra_asociadas': resumen_ocs_asociadas
                },
                'responsables': {
                    'supervisor': orden_produccion_data.get('supervisor_nombre', 'N/A'),
                    'supervisor_calidad': orden_produccion_data.get('aprobador_calidad_nombre', 'N/A'),
                    'operario': orden_produccion_data.get('operario_nombre', 'N/A')
                }
            }

            return {'success': True, 'data': response_data}

        except Exception as e:
            import logging
            logging.error(f"Error en get_trazabilidad_orden_produccion: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def obtener_datos_trazabilidad(self, tipo_entidad, id_entidad):
        """
        Endpoint unificado para obtener todos los datos de trazabilidad 
        para una entidad específica (lote_insumo, lote_producto, etc.).
        El modelo se encarga de construir toda la data necesaria.
        """
        try:
            data = None
            if tipo_entidad == 'lote_insumo':
                data = self.trazabilidad_model.obtener_trazabilidad_completa_lote_insumo(id_entidad)
            elif tipo_entidad == 'lote_producto':
                data = self.trazabilidad_model.obtener_trazabilidad_completa_lote_producto(id_entidad)
            elif tipo_entidad == 'orden_produccion':
                data = self.trazabilidad_model.obtener_trazabilidad_completa_orden_produccion(id_entidad)
            # Se pueden agregar más entidades en el futuro (pedido, orden_compra, etc.)

            if data:
                return {"success": True, "data": data}, 200
            else:
                return {"success": False, "error": f"No se encontraron datos de trazabilidad para {tipo_entidad} con ID {id_entidad}."}, 404

        except Exception as e:
            logger.error(f"Error en trazabilidad para {tipo_entidad} {id_entidad}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno del servidor: {str(e)}"}, 500
