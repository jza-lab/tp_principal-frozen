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

# Version 2.3 de Permisos - Ajustes para SUPERVISOR_CALIDAD
CANONICAL_PERMISSION_MAP = {
    # Módulo: Acceso General
    'dashboard_acceder': ['ADMIN', 'VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'RRHH', 'GERENTE', 'IT'],

    # Módulo: Administración y Configuración
    'admin_gestion_sistema': ['ADMIN', 'IT'],
    'admin_gestion_personal': ['ADMIN','RRHH', 'IT'],
    'consultar_empleados': ['RRHH', 'ADMIN', 'IT', 'SUPERVISOR', 'GERENTE'],
    'admin_configuracion_sistema': ['IT', 'GERENTE', 'RRHH'],
    'gestionar_proveedores': ['ADMIN'],
    'gestionar_autorizaciones': ['ADMIN', 'SUPERVISOR', 'RRHH'],
    'admin_acceder_consultas': ['GERENTE', 'VENDEDOR'],
    'admin_actualizar_precios_excel': ['ADMIN', 'VENDEDOR'],

    # Módulo: Comercial (Ventas y Clientes)
    'logistica_gestion_ov': ['VENDEDOR'], # Permiso para que Vendedor gestione Órdenes de Venta
    'planificar_ov': ['VENDEDOR', 'SUPERVISOR', 'GERENTE'],
    'gestionar_clientes': ['VENDEDOR'],
    'finanzas_ver_precios_costos': ['VENDEDOR', 'SUPERVISOR', 'GERENTE'],

    # Módulo: Producción
    'crear_orden_de_produccion': ['SUPERVISOR'],
    'aprobar_orden_de_produccion': ['SUPERVISOR'],
    'gestionar_orden_de_produccion': ['SUPERVISOR'], # Editar, cambiar estado, etc.
    'produccion_ejecucion': ['SUPERVISOR_CALIDAD','OPERARIO','SUPERVISOR'], # Asignar operarios, mover en kanban
    'produccion_consulta': ['OPERARIO', 'SUPERVISOR', 'GERENTE', 'SUPERVISOR_CALIDAD'],
    'consultar_plan_de_produccion': ['OPERARIO', 'SUPERVISOR', 'GERENTE','SUPERVISOR_CALIDAD'],

    # Módulo: Almacén e Inventario
    'gestionar_catalogo_de_productos': ['SUPERVISOR', 'ADMIN', 'GERENTE'],
    'gestionar_catalogo_insumos': ['SUPERVISOR', 'ADMIN'], # Crear, editar, inhabilitar insumos
    'gestionar_inventario': ['SUPERVISOR'], # Registrar ingresos y egresos de stock
    'gestionar_lotes': ['SUPERVISOR', 'SUPERVISOR_CALIDAD'], # Crear y gestionar lotes de productos
    'almacen_consulta_stock': [ 'VENDEDOR', 'SUPERVISOR', 'GERENTE', 'SUPERVISOR_CALIDAD'],
    'registrar_ingreso_de_materia_prima': ['ADMIN'],
    'almacen_ver_registrar': ['VENDEDOR', 'SUPERVISOR'],
    'almacen_ver_insumos': ['OPERARIO', 'SUPERVISOR', 'GERENTE'],

    # Módulo: Calidad
    'controlar_calidad_lotes': ['SUPERVISOR', 'SUPERVISOR_CALIDAD'], # Realizar controles de calidad
    'aprobar_lotes_calidad': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE'], # Aprobación final de calidad
    'produccion_control_proceso': ['SUPERVISOR_CALIDAD', 'SUPERVISOR', 'GERENTE'],
    'registrar_desperdicios': ['SUPERVISOR_CALIDAD'],
    'consultar_reportes_calidad': ['SUPERVISOR_CALIDAD'],

    # Módulo: Órdenes de Compra (OC) y Logística
    'crear_orden_de_compra': ['SUPERVISOR', 'ADMIN'],
    'consultar_ordenes_de_compra': ['SUPERVISOR_CALIDAD','SUPERVISOR', 'ADMIN', 'GERENTE', 'VENDEDOR'],
    'realizar_control_de_calidad_insumos': ['SUPERVISOR_CALIDAD'],
    'editar_orden_de_compra': ['SUPERVISOR', 'ADMIN'],
    'aprobar_orden_de_compra': ['SUPERVISOR','GERENTE'],
    'gestionar_recepcion_orden_compra': ['SUPERVISOR_CALIDAD', 'DEV'],
    'logistica_recepcion_oc': ['ADMIN', 'SUPERVISOR', 'GERENTE'],
    'logistica_supervision': ['SUPERVISOR', 'GERENTE'],

    # Módulo: Gerencia y Supervisión General
    'aprobar_orden_de_venta': ['GERENTE'],
    'inactivar_entidad': ['GERENTE'],
    'consultar_logs_o_auditoria': ['IT', 'GERENTE', 'RRHH'],
    'consultar_trazabilidad_completa': ['GERENTE', 'SUPERVISOR_CALIDAD'],

    # Módulo: Alertas y Reclamos
    'ver_alertas': ['SUPERVISOR', 'IT', 'GERENTE', 'SUPERVISOR_CALIDAD'],
    'configurar_alertas': ['SUPERVISOR', 'IT', 'GERENTE'],
    'gestionar_reclamos': ['ADMIN', 'VENDEDOR', 'GERENTE'],
}


def get_allowed_roles_for_action(action_name: str) -> list:
    """
    Devuelve la lista de códigos de rol permitidos para una acción específica.
    Asegura que el GERENTE tenga acceso de lectura a todas las acciones de consulta.
    """
    allowed_roles = CANONICAL_PERMISSION_MAP.get(action_name, [])

    # El GERENTE tiene acceso total de LECTURA.
    # Si la acción es de consulta y el Gerente no está, se añade.
    is_read_action = action_name.startswith(('consultar_', 'ver_')) or action_name.endswith('_consulta')
    if is_read_action and 'GERENTE' not in allowed_roles:
        return allowed_roles + ['GERENTE']

    return allowed_roles
