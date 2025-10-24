"""
Este módulo centraliza los mapas de permisos y roles de la aplicación.
Define la relación entre acciones y los roles que pueden realizarlas,
así como mapas de IDs a códigos para sectores y roles.

NOTA: El diccionario CANONICAL_PERMISSION_MAP es la única fuente de verdad
para la lógica de permisos basada en roles y acciones.
"""

SECTOR_MAP = {
    1: 'ADMINISTRACION',
    2: 'ALMACEN',
    3: 'LOGISTICA',
    4: 'CALIDAD',
    5: 'PRODUCCION',
    6: 'DESARROLLO',
}

ROLE_MAP = {
    1: 'ADMIN',
    2: 'VENDEDOR',
    3: 'OPERARIO',
    4: 'SUPERVISOR',
    5: 'SUPERVISOR_CALIDAD',
    6: 'RRHH',
    7: 'GERENTE',
    8: 'IT',
    9: 'DEV',
}

CANONICAL_PERMISSION_MAP = {
    # Rol: ADMIN
    'acceder_al_panel_principal': ['ADMIN', 'DEV', 'IT', 'GERENTE', 'RRHH', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'VENDEDOR', 'OPERARIO'],
    'consultar_reportes_generales': ['ADMIN', 'DEV'],
    'emitir_facturas': ['ADMIN', 'DEV'],
    'emitir_notas_de_credito': ['ADMIN', 'DEV'],
    'consultar_historial_de_pagos': ['ADMIN', 'DEV'],
    'consultar_stock_de_productos': ['ADMIN', 'VENDEDOR', 'DEV'],
    'registrar_ingreso_de_materia_prima': ['ADMIN', 'DEV'],
    'consultar_ordenes_de_produccion': ['ADMIN', 'SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'consultar_reportes_de_control': ['ADMIN', 'DEV'],
    'consultar_empleados': ['ADMIN', 'RRHH', 'IT''DEV'],

    # Rol: VENDEDOR
    'crear_orden_de_venta': ['VENDEDOR', 'DEV'],
    'modificar_orden_de_venta': ['VENDEDOR', 'DEV'],
    'consultar_historial_de_clientes': ['VENDEDOR', 'DEV', 'ADMIN'],
    'emitir_factura_de_venta': ['VENDEDOR', 'DEV'],
    'consultar_historial_crediticio_de_clientes': ['VENDEDOR', 'ADMIN', 'DEV'],
    'consultar_estado_de_produccion_asociada': ['VENDEDOR', 'DEV'],
    'consultar_disponibilidad_de_productos': ['VENDEDOR', 'DEV'],

    # Rol: OPERARIO
    'consultar_ordenes_asignadas': ['OPERARIO', 'DEV'],
    'registrar_etapa_de_produccion': ['OPERARIO', 'DEV'],
    'consultar_resultados_de_control': ['OPERARIO', 'DEV'],
    'consultar_stock_de_insumos': ['OPERARIO', 'DEV'],
    'notificar_de_baja_cantidad_de_insumos': ['OPERARIO', 'DEV'],

    # Rol: SUPERVISOR
    'crear_orden_de_produccion': ['SUPERVISOR', 'DEV'],
    'supervisar_avance_de_etapas': ['SUPERVISOR', 'DEV'],
    'reasignar_OPERARIOs_a_una_orden': ['SUPERVISOR', 'DEV'],
    'cerrar_orden_de_produccion': ['SUPERVISOR', 'DEV'],
    'consultar_stock': ['SUPERVISOR', 'DEV'],
    'solicitar_reposicion_de_insumos': ['SUPERVISOR', 'DEV'],
    'crear_orden_de_compra': ['SUPERVISOR', 'DEV'],
    'aprobar_orden_de_compra': ['SUPERVISOR', 'DEV', 'ADMIN'],
    'consultar_control_de_calidad': ['SUPERVISOR', 'VENDEDOR', 'DEV'],

    # Rol: SUPERVISOR_CALIDAD
    'crear_control_de_calidad_por_lote': ['SUPERVISOR_CALIDAD', 'DEV'],
    'registrar_resultados_de_control': ['SUPERVISOR_CALIDAD', 'DEV'],
    'registrar_desperdicios': ['SUPERVISOR_CALIDAD', 'DEV'],
    'consultar_reportes_historicos': ['SUPERVISOR_CALIDAD', 'DEV'],
    'ver_trazabilidad_de_materias_primas': ['SUPERVISOR_CALIDAD', 'DEV'],
    'consultar_stock_de_lotes': ['SUPERVISOR_CALIDAD', 'DEV'],

    # Rol: Gerente General
    'consultar_reportes_de_produccion': ['GERENTE', 'DEV'],
    'consultar_reportes_financieros': ['GERENTE', 'DEV'],
    'consultar_metricas_de_stock': ['GERENTE', 'DEV'],
    'consultar_ordenes_de_venta': ['GERENTE', 'VENDEDOR', 'DEV'],
    'consultar_ordenes_de_compra': ['GERENTE', 'DEV'],
    'consultar_trazabilidad_completa': ['GERENTE', 'DEV'],
    'consultar_indicadores_de_calidad': ['GERENTE', 'DEV'],

    # Rol: Recursos Humanos
    'crear_empleado': ['RRHH', 'DEV'],
    'modificar_empleado': ['RRHH', 'IT','DEV'],
    'eliminar_empleado': ['RRHH', 'DEV'],
    'consultar_OPERARIOs': ['RRHH', 'IT', 'DEV'],

    # Rol: IT / Soporte
    'configurar_usuarios_y_roles': ['IT', 'DEV'],
    'modificar_parametros_del_sistema': ['IT', 'DEV'],
    'realizar_mantenimiento_y_backups': ['IT', 'DEV'],
    'consultar_logs_o_auditoria': ['IT', 'GERENTE', 'SUPERVISOR', 'ADMIN', 'DEV'],

    # Permisos nuevos para asignación de roles
    'gestionar_catalogo_de_productos': ['SUPERVISOR', 'GERENTE'],
    'consultar_catalogo_de_insumos': ['OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE'],
    'aprobar_orden_de_venta': ['SUPERVISOR', 'GERENTE', 'VENDEDOR'], 
    'gestionar_clientes': ['VENDEDOR', 'ADMIN', 'GERENTE'], 
    'gestionar_proveedores': ['ADMIN'], 
    'gestionar_catalogo_de_insumos': ['SUPERVISOR', 'GERENTE'], 
    'rechazar_orden_de_compra': ['SUPERVISOR', 'GERENTE'],
    'ver_panel_notificaciones': ['IT', 'DEV', 'ADMIN'],
    'gestionar_autorizaciones': ['ADMIN','DEV'],
    'registrar_lote_de_producto': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'ADMIN', 'DEV'],
    'ver_alertas_topbar': ['GERENTE', 'SUPERVISOR', 'DEV'],

}

def get_allowed_roles_for_action(action_name: str) -> list:
    """
    Devuelve la lista de códigos de rol permitidos para una acción específica.
    """
    return CANONICAL_PERMISSION_MAP.get(action_name, [])
