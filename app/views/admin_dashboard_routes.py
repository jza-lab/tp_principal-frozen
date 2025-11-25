from datetime import date, timedelta, datetime
from flask import Blueprint, render_template
from flask_jwt_extended import jwt_required, get_jwt
from app.controllers.usuario_controller import UsuarioController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.controllers.pedido_controller import PedidoController
from app.controllers.notificación_controller import NotificacionController
from app.controllers.inventario_controller import InventarioController
from app.controllers.lote_producto_controller import LoteProductoController
from app.controllers.cliente_controller import ClienteController # (NUEVO)
from app.controllers.consulta_controller import ConsultaController
from app.utils.decorators import permission_required
from app.models.reclamo import ReclamoModel

# Blueprint para el dashboard de administración
admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')

@admin_dashboard_bp.route('/')
@jwt_required()
@permission_required(accion='dashboard_acceder')
def index():
    """Página principal del panel de administración."""
    usuario_controller = UsuarioController()
    orden_produccion_controller = OrdenProduccionController()
    orden_venta_controller = PedidoController()
    notificacion_controller = NotificacionController()
    inventario_controller = InventarioController()
    lote_producto_controller = LoteProductoController()
    cliente_controller = ClienteController()
    current_user = get_jwt()
    user_roles = current_user.get('roles', [])
    user_id = current_user.get('id_usuario', None)
    is_operario = 'OPERARIO' in user_roles
    is_supervisor_calidad = 'SUPERVISOR_CALIDAD' in user_roles
    
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

    filtros = {'estado': 'LISTA PARA PRODUCIR'}
    if is_operario:
        filtros['operario_responsable_id'] = user_id
    respuesta_ordenes, _ = orden_produccion_controller.obtener_ordenes(filtros)
    ordenes_listas_para_producir = respuesta_ordenes.get('data', [])
    
    # Obtener órdenes en espera de insumo
    filtros_espera = {'estado': 'EN ESPERA'}
    if is_operario:
        filtros_espera['operario_responsable_id'] = user_id
    respuesta_ordenes_espera, _ = orden_produccion_controller.obtener_ordenes(filtros_espera)
    ordenes_en_espera_de_insumo = respuesta_ordenes_espera.get('data', [])


    asistencia = usuario_controller.obtener_porcentaje_asistencia()
    
    notificaciones_utc = notificacion_controller.obtener_notificaciones_no_leidas()
    notificaciones = []
    for notif in notificaciones_utc:
        if isinstance(notif.get('created_at'), str):
            # Convertir el string a datetime antes de restar
            notif['created_at'] = datetime.fromisoformat(notif['created_at']) - timedelta(hours=3)
        notificaciones.append(notif)
    
    insumos_bajo_stock_resp, _ = inventario_controller.obtener_insumos_bajo_stock()
    insumos_bajo_stock_list = insumos_bajo_stock_resp.get('data', [])
    alertas_stock_count = inventario_controller.obtener_conteo_alertas_stock()

    productos_sin_lotes_resp, _ = lote_producto_controller.obtener_conteo_productos_sin_lotes()
    data_sin_lotes = productos_sin_lotes_resp.get('data', {})
    productos_sin_lotes_count = data_sin_lotes.get('conteo_sin_lotes', 0) 
    productos_sin_lotes_list = data_sin_lotes.get('productos_sin_lotes', [])


    # Órdenes de Venta Pendientes
    respuesta_ov_pendientes, _ = orden_venta_controller.obtener_pedidos({'estado': 'PENDIENTE'})
    ordenesventa_pendientes_list = respuesta_ov_pendientes.get('data', [])
    ordenesventa_pendientes_count = len(ordenesventa_pendientes_list)

    # Órdenes de Venta Rechazadas
    respuesta_ov_rechazadas, _ = orden_venta_controller.obtener_pedidos({'estado': 'CANCELADO'})
    ordenesventa_rechazadas_list = respuesta_ov_rechazadas.get('data', [])
    ordenesventa_rechazadas_count = len(ordenesventa_rechazadas_list)

    # Órdenes de Producción en Proceso
    filtros_proceso = {'estado': 'EN_PROCESO'}
    if is_operario:
        filtros_proceso['operario_responsable_id'] = user_id
    respuesta_op_proceso, _ = orden_produccion_controller.obtener_ordenes(filtros_proceso)
    ordenesproduccion_proceso_list = respuesta_op_proceso.get('data', [])
    ordenesproduccion_proceso_count = len(ordenesproduccion_proceso_list)

    lotes_vencimiento_count = inventario_controller.obtener_conteo_vencimientos()
    productos_sin_lotes_resp, _ = lote_producto_controller.obtener_conteo_productos_sin_lotes()

    # Conteo de clientes pendientes de aprobación
    pending_client_count = 0
    respuesta_clientes_pendientes, _ = cliente_controller.obtener_conteo_clientes_pendientes()
    if respuesta_clientes_pendientes.get('success'):
        pending_client_count = respuesta_clientes_pendientes.get('data', {}).get('count', 0)
    
    reclamo_stats = ReclamoModel().get_count_by_estado('pendiente')
    conteo_reclamos = 0
    if reclamo_stats.get('success'):
        conteo_reclamos = reclamo_stats.get('count', 0)

    consulta_controller = ConsultaController()
    conteo_consultas = consulta_controller.obtener_conteo_consultas_pendientes()
    
    # Insumos en cuarentena (ahora obtiene lista y conteo)
    insumos_cuarentena_result = inventario_controller.obtener_lotes_y_conteo_insumos_en_cuarentena()
    insumos_en_cuarentena = insumos_cuarentena_result.get('count', 0)
    insumos_en_cuarentena_lista = insumos_cuarentena_result.get('data', [])

    # Indicadores para Supervisor de Calidad
    lotes_pendientes_result = lote_producto_controller.obtener_lotes_y_conteo_por_estado('PENDIENTE_CALIDAD')
    lotes_pendientes_control = lotes_pendientes_result.get('count', 0)
    lotes_pendientes_control_lista = lotes_pendientes_result.get('data', [])

    productos_rechazados_result = lote_producto_controller.obtener_lotes_y_conteo_por_estado('CUARENTENA')
    productos_rechazados = productos_rechazados_result.get('count', 0)
    productos_rechazados_lista = productos_rechazados_result.get('data', [])
    
    lotes_vencimiento_result = lote_producto_controller.obtener_lotes_y_conteo_vencimientos()
    lotes_producto_vencimiento_count = lotes_vencimiento_result.get('count', 0)
    lotes_producto_vencimiento_lista = lotes_vencimiento_result.get('data', [])
    
    for lote in lotes_producto_vencimiento_lista:
        if isinstance(lote.get('fecha_vencimiento'), str):
            lote['fecha_vencimiento'] = datetime.fromisoformat(lote['fecha_vencimiento'].split('T')[0])

    lotes_sin_trazabilidad = lote_producto_controller.obtener_conteo_lotes_sin_trazabilidad()
    ordenes_reabiertas = orden_produccion_controller.obtener_conteo_ordenes_reabiertas()

    return render_template('dashboard/index.html', 
                           insumos_en_cuarentena=insumos_en_cuarentena,
                           insumos_en_cuarentena_lista=insumos_en_cuarentena_lista,
                           lotes_pendientes_control=lotes_pendientes_control,
                           lotes_pendientes_control_lista=lotes_pendientes_control_lista,
                           productos_rechazados=productos_rechazados,
                           productos_rechazados_lista=productos_rechazados_lista,
                           lotes_producto_vencimiento_lista=lotes_producto_vencimiento_lista,
                           lotes_sin_trazabilidad=lotes_sin_trazabilidad,
                           ordenes_reabiertas=ordenes_reabiertas,
                           conteo_consultas_pendientes=conteo_consultas,
                           asistencia=asistencia,
                           ordenes_pendientes=ordenes_pendientes,
                           ordenes_aprobadas=ordenes_listas_para_producir,
                           ordenes_en_espera_de_insumo=ordenes_en_espera_de_insumo,
                           ordenes_totales=ordenes_totales,
                           notificaciones=notificaciones,
                           alertas_stock_count=alertas_stock_count,
                           insumos_bajo_stock_list=insumos_bajo_stock_list,
                           productos_sin_lotes_count=productos_sin_lotes_count,
                           productos_sin_lotes_list=productos_sin_lotes_list,
                           ordenesventa_pendientes=ordenesventa_pendientes_count,
                           ordenesventa_pendientes_list=ordenesventa_pendientes_list,
                           ordenesventa_rechazadas=ordenesventa_rechazadas_count,
                           ordenesventa_rechazadas_list=ordenesventa_rechazadas_list,
                           ordenesproduccion_proceso_count=ordenesproduccion_proceso_count,
                           ordenesproduccion_proceso_list=ordenesproduccion_proceso_list,
                           lotes_vencimiento_count=lotes_vencimiento_count,
                           conteo_reclamos_pendientes=conteo_reclamos,
                           lotes_producto_vencimiento_count=lotes_producto_vencimiento_count,
                           pending_client_count=pending_client_count,
                           is_operario=is_operario,
                           is_supervisor_calidad=is_supervisor_calidad)