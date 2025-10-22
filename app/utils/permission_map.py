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
    'crear_usuarios': ['ADMIN', 'IT', 'DEV'],
    'modificar_usuarios': ['ADMIN', 'IT', 'DEV'],
    'inactivar_usuarios': ['ADMIN', 'RRHH', 'DEV'],
    'asignar_roles_permisos': ['ADMIN', 'IT', 'DEV'],
    'config_param_sistema': ['ADMIN', 'IT', 'DEV'],
    'solicitar_permisos': ['ADMIN', 'OPERARIO', 'SUPERVISOR', 'RRHH', 'IT', 'DEV'],
    'actualizar_lista_precios_prov': ['ADMIN', 'DEV'],
    'autenticacion': ['ADMIN', 'OPERARIO', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'gestionar_proveedores': ['ADMIN', 'DEV'],
    'registrar_ingresos_stock': ['ADMIN', 'SUPERVISOR', 'DEV'],
    'recepcionar_compras': ['ADMIN', 'DEV'],
    'revision_final_recepcion': ['ADMIN', 'SUPERVISOR_CALIDAD', 'DEV'],
    'ver_reportes_basicos': ['VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'ver_reportes_produccion': ['VENDEDOR', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'ver_indicadores_eficiencia': ['VENDEDOR', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'ver_reportes_stock': ['VENDEDOR', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'ver_reportes_financieros': ['VENDEDOR', 'GERENTE', 'DEV'],
    'exportar_reportes': ['VENDEDOR', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'ver_dashboard': ['VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'ADMIN', 'IT', 'RRHH', 'DEV'],
    'actualizar_precios_proveedor': ['VENDEDOR', 'DEV'],
    'ver_materias_primas': ['VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'ver_stock_actual': ['VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'ver_alertas_stock': ['VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'ver_ordenes_compra': ['VENDEDOR', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'crear_ordenes_compra': ['VENDEDOR', 'GERENTE', 'DEV'],
    'modificar_ordenes_compra': ['VENDEDOR', 'GERENTE', 'DEV'],
    'cancelar_ordenes_compra': ['VENDEDOR', 'GERENTE', 'DEV'],
    'ver_ordenes_venta': ['VENDEDOR', 'GERENTE', 'SUPERVISOR', 'DEV'],
    'crear_ordenes_venta': ['VENDEDOR', 'GERENTE', 'DEV'],
    'modificar_ordenes_venta': ['VENDEDOR', 'GERENTE', 'DEV'],
    'cancelar_ordenes_venta': ['VENDEDOR', 'GERENTE', 'DEV'],
    'registrar_envios': ['VENDEDOR', 'SUPERVISOR', 'DEV'],
    'registrar_datos_calidad_basicos': ['OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'DEV'],
    'ver_ordenes_produccion': ['OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'VENDEDOR', 'DEV'],
    'iniciar_produccion': ['OPERARIO', 'SUPERVISOR', 'DEV'],
    'registrar_inicio_etapa': ['OPERARIO', 'SUPERVISOR', 'DEV'],
    'registrar_fin_etapa': ['OPERARIO', 'SUPERVISOR', 'DEV'],
    'registrar_desperdicios': ['OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'DEV'],
    'ver_progreso_tiempo_real': ['OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'DEV'],
    'ver_info_empleados': ['SUPERVISOR', 'RRHH', 'GERENTE', 'DEV'],
    'registrar_asistencias': ['SUPERVISOR', 'RRHH', 'DEV'],
    'gestionar_turnos': ['SUPERVISOR', 'RRHH', 'GERENTE', 'DEV'],
    'aprobar_permisos': ['SUPERVISOR', 'RRHH', 'GERENTE', 'DEV'],
    'ver_consumo_materias_primas': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'ver_indicadores_desperdicio': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'config_param_negocio': ['SUPERVISOR', 'GERENTE', 'IT', 'DEV'],
    'crear_materias_primas': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'modificar_materias_primas': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'eliminar_materias_primas': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'registrar_egresos_stock': ['SUPERVISOR', 'DEV'],
    'config_alertas_stock': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'gestionar_lotes_vencimientos': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'asignar_materias_primas_ordenes': ['SUPERVISOR', 'DEV'],
    'config_umbrales_stock': ['SUPERVISOR', 'DEV'],
    'crear_ordenes_compra_manual': ['SUPERVISOR', 'DEV'],
    'realizar_control_calidad': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'DEV'],
    'aprobar_lotes': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'DEV'],
    'rechazar_lotes': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'DEV'],
    'ver_historial_controles': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'registrar_no_conformidades': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'DEV'],
    'ver_calidad_insumos': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'crear_ordenes_produccion': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'modificar_ordenes_produccion': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'aprobar_ordenes_produccion': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'cancelar_ordenes_produccion': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'pausar_produccion': ['SUPERVISOR', 'DEV'],
    'modificar_registros_historicos': ['SUPERVISOR', 'DEV'],
    'control_calidad_lote': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'DEV'],
    'aprobar_rechazar_lotes': ['SUPERVISOR', 'DEV'],
    'config_modos_linea': ['SUPERVISOR', 'DEV'],
    'config_param_calidad': ['SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'modificar_info_empleados': ['RRHH', 'GERENTE', 'DEV'],
    'monitoreo_tecnico_ver_logs': ['GERENTE', 'IT', 'DEV'],
    'ver_reportes_estrategicos': ['GERENTE', 'DEV'],
    'inactivar_proveedores_clientes': ['GERENTE', 'ADMIN', 'DEV'],
    'aprobar_ordenes_compra': ['GERENTE', 'DEV'],
    'aprobar_ordenes_venta': ['GERENTE', 'DEV'],
    'gestionar_backups': ['IT', 'DEV']
}

def get_allowed_roles_for_action(action_name: str) -> list:
    """
    Devuelve la lista de códigos de rol permitidos para una acción específica.
    """
    return CANONICAL_PERMISSION_MAP.get(action_name, [])