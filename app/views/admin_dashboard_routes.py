from datetime import date, timedelta
from flask import Blueprint, session, render_template
from app.controllers.usuario_controller import UsuarioController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.notificación_controller import NotificacionController
from app.controllers.inventario_controller import InventarioController
from app.controllers.lote_producto_controller import LoteProductoController
from app.permisos import permission_required

# Blueprint para el dashboard de administración
admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')

# Instanciar controladores
usuario_controller = UsuarioController()
orden_produccion_controller = OrdenProduccionController()
notificacion_controller = NotificacionController()
inventario_controller = InventarioController()
lote_producto_controller = LoteProductoController()

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
    respuesta, _ = orden_produccion_controller.obtener_cantidad_ordenes_estado("EN_PROCESO", hoy)
    ordenes_pendientes = respuesta.get('data', {}).get('cantidad', 0)

    respuesta2, _ = orden_produccion_controller.obtener_cantidad_ordenes_estado("APROBADA")
    respuesta3, _ = orden_produccion_controller.obtener_cantidad_ordenes_estado("COMPLETADA")
    
    cantidad_aprobadas = respuesta2.get('data', {}).get('cantidad', 0)
    cantidad_completadas = respuesta3.get('data', {}).get('cantidad', 0)
    ordenes_totales = int(cantidad_aprobadas) + int(cantidad_completadas)

    filtros = {'estado': 'APROBADA', 'fecha_planificada_desde': fecha_inicio_iso, 'fecha_planificada_hasta': fecha_fin_iso}
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
    
    user_permissions = session.get('permisos', {})

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
                           user_permissions=user_permissions)
