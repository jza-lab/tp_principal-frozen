from datetime import date, timedelta
from flask import Blueprint, session, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.pedido_controller import PedidoController
from app.controllers.notificación_controller import NotificacionController
from app.controllers.inventario_controller import InventarioController
from app.controllers.lote_producto_controller import LoteProductoController
from app.utils.decorators import permission_required

# Blueprint para el dashboard de administración
admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')

# Instanciar controladores
usuario_controller = UsuarioController()
orden_produccion_controller = OrdenProduccionController()
orden_venta_controller = PedidoController()
notificacion_controller = NotificacionController()
inventario_controller = InventarioController()
lote_producto_controller = LoteProductoController()
alertas_stock_count = inventario_controller.obtener_conteo_alertas_stock()

@admin_dashboard_bp.route('/')
@permission_required(accion='ver_dashboard')
def index():
    """Página principal del panel de administración."""
    hoy = date.today()
    dias_restar = hoy.weekday()
    fecha_inicio_semana = hoy - timedelta(days=dias_restar)
    fecha_fin_semana = fecha_inicio_semana + timedelta(days=6)
    fecha_inicio_iso = fecha_inicio_semana.isoformat()
    fecha_fin_iso = fecha_fin_semana.isoformat()

    # NOTA: Esta lógica compleja debería moverse a un DashboardController en el futuro.
    # Por ahora, se mantiene aquí para cumplir con la primera fase de la refactorización.
    respuesta, _ = orden_produccion_controller.obtener_cantidad_ordenes_estado("EN_PROCESO")
    ordenes_pendientes = respuesta.get('data', {}).get('cantidad', 0)

    respuesta2, _ = orden_produccion_controller.obtener_cantidad_ordenes_estado("LISTA PARA PRODUCIR")
    respuesta3, _ = orden_produccion_controller.obtener_cantidad_ordenes_estado("COMPLETADA")
    
    cantidad_aprobadas = respuesta2.get('data', {}).get('cantidad', 0)
    cantidad_completadas = respuesta3.get('data', {}).get('cantidad', 0)
    ordenes_totales = int(cantidad_aprobadas) + int(cantidad_completadas)

    filtros = {'estado': 'LISTA PARA PRODUCIR', 'fecha_planificada_desde': fecha_inicio_iso, 'fecha_planificada_hasta': fecha_fin_iso}
    respuesta_ordenes, _ = orden_produccion_controller.obtener_ordenes(filtros)
    ordenes_aprobadas = respuesta_ordenes.get('data', [])

    asistencia = usuario_controller.obtener_porcentaje_asistencia()
    notificaciones = notificacion_controller.obtener_notificaciones_no_leidas()
    
    insumos_bajo_stock_resp, _ = inventario_controller.obtener_insumos_bajo_stock()
    insumos_bajo_stock_list = insumos_bajo_stock_resp.get('data', [])
    alertas_stock_count = inventario_controller.obtener_conteo_alertas_stock()

    productos_sin_lotes_resp, _ = lote_producto_controller.obtener_conteo_productos_sin_lotes()
    data_sin_lotes = productos_sin_lotes_resp.get('data', {})
    productos_sin_lotes_count = data_sin_lotes.get('conteo_sin_lotes', 0) 
    productos_sin_lotes_list = data_sin_lotes.get('productos_sin_lotes', [])


    respuesta4, _ = orden_venta_controller.obtener_cantidad_pedidos_estado("PENDIENTE")
    ordenesventa_pendientes = respuesta4.get('data', {}).get('cantidad', 0)
    
    respuesta5, _ = orden_venta_controller.obtener_cantidad_pedidos_rechazados_recientes()
    ordenesventa_rechazadas = respuesta5.get('data', {}).get('cantidad', 0)

    lotes_vencimiento_count = inventario_controller.obtener_conteo_vencimientos() 
    productos_sin_lotes_resp, _ = lote_producto_controller.obtener_conteo_productos_sin_lotes()

    lotes_producto_vencimiento_count = lote_producto_controller.obtener_conteo_vencimientos() 

    user_role = session.get('rol')
    user_permissions = session.get('permisos', {})

    is_dev = (user_role == 'DEV')
    is_gerente = (user_role == 'GERENTE')

    user_permissions['is_gerente'] = is_gerente
    user_permissions['is_dev'] = is_dev # Agregar bandera is_dev para desarrolladores
    
    return render_template('dashboard/index.html', 
                           asistencia=asistencia,
                           ordenes_pendientes=ordenes_pendientes,
                           ordenes_aprobadas=ordenes_aprobadas,
                           ordenes_totales=ordenes_totales,
                           notificaciones=notificaciones,
                           alertas_stock_count=alertas_stock_count,
                           insumos_bajo_stock_list=insumos_bajo_stock_list,
                           productos_sin_lotes_count=productos_sin_lotes_count,
                           productos_sin_lotes_list=productos_sin_lotes_list,
                           ordenesventa_pendientes=ordenesventa_pendientes,
                           ordenesventa_rechazadas=ordenesventa_rechazadas,
                           lotes_vencimiento_count=lotes_vencimiento_count,
                           lotes_producto_vencimiento_count=lotes_producto_vencimiento_count,
                           user_permissions=user_permissions)
