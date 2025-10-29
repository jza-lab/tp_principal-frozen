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

# Version 2.2 de Permisos - Ajustes para SUPERVISOR
CANONICAL_PERMISSION_MAP = {
    # Módulo: Acceso General
    'dashboard_acceder': ['ADMIN', 'VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'RRHH', 'GERENTE', 'IT'],

    # Módulo: Administración y Configuración
    'admin_gestion_sistema': ['ADMIN', 'IT'],
    'admin_gestion_personal': ['RRHH', 'ADMIN', 'IT'],
    'consultar_empleados': ['RRHH', 'ADMIN', 'IT', 'SUPERVISOR', 'GERENTE'],
    'admin_configuracion_sistema': ['IT', 'GERENTE'],
    'gestionar_proveedores': ['ADMIN'],
    'gestionar_autorizaciones': ['ADMIN', 'SUPERVISOR'],
    'admin_acceder_consultas': ['GERENTE', 'VENDEDOR'],
    'admin_actualizar_precios_excel': ['ADMIN', 'VENDEDOR'],

    # Módulo: Comercial (Ventas y Clientes)
    'logistica_gestion_ov': ['VENDEDOR'], # Permiso para que Vendedor gestione Órdenes de Venta
    'gestionar_clientes': ['VENDEDOR'],
    'finanzas_ver_precios_costos': ['VENDEDOR', 'SUPERVISOR', 'GERENTE'],

    # Módulo: Producción
    'crear_orden_de_produccion': ['SUPERVISOR'],
    'aprobar_orden_de_produccion': ['SUPERVISOR'],
    'gestionar_orden_de_produccion': ['SUPERVISOR'], # Editar, cambiar estado, etc.
    'produccion_ejecucion': ['OPERARIO', 'SUPERVISOR'], # Asignar operarios, mover en kanban
    'produccion_consulta': ['OPERARIO', 'SUPERVISOR', 'GERENTE'],
    'consultar_plan_de_produccion': ['OPERARIO', 'SUPERVISOR', 'GERENTE'],

    # Módulo: Almacén e Inventario
    'gestionar_catalogo_insumos': ['SUPERVISOR', 'ADMIN'], # Crear, editar, inhabilitar insumos
    'gestionar_inventario': ['SUPERVISOR'], # Registrar ingresos y egresos de stock
    'gestionar_lotes': ['SUPERVISOR'], # Crear y gestionar lotes de productos
    'almacen_consulta_stock': ['VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'GERENTE'],
    'registrar_ingreso_de_materia_prima': ['ADMIN'],
    'almacen_ver_registrar': ['VENDEDOR', 'SUPERVISOR'],
    'almacen_ver_insumos': ['SUPERVISOR_CALIDAD', 'SUPERVISOR', 'GERENTE', 'VENDEDOR'],

    # Módulo: Calidad
    'controlar_calidad_lotes': ['SUPERVISOR', 'SUPERVISOR_CALIDAD'], # Realizar controles de calidad
    'aprobar_lotes_calidad': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE'], # Aprobación final de calidad
    'produccion_control_proceso': ['SUPERVISOR_CALIDAD', 'SUPERVISOR', 'GERENTE'],

    # Módulo: Órdenes de Compra (OC) y Logística
    'crear_orden_de_compra': ['SUPERVISOR', 'ADMIN'],
    'consultar_ordenes_de_compra': ['SUPERVISOR', 'ADMIN', 'GERENTE', 'VENDEDOR'],
    'editar_orden_de_compra': ['SUPERVISOR', 'ADMIN'],
    'aprobar_orden_de_compra': ['GERENTE'], # <- NO TOCAR: Solo GERENTE aprueba
    'logistica_recepcion_oc': ['ADMIN', 'SUPERVISOR', 'GERENTE'],
    'logistica_supervision': ['SUPERVISOR', 'GERENTE'],

    # Módulo: Gerencia y Supervisión General
    'aprobar_orden_de_venta': ['GERENTE'],
    'inactivar_entidad': ['GERENTE'],
    'consultar_logs_o_auditoria': ['IT', 'GERENTE'],
    'consultar_trazabilidad_completa': ['GERENTE', 'SUPERVISOR_CALIDAD'],

    # Módulo: Alertas y Reclamos
    'ver_alertas': ['SUPERVISOR', 'IT', 'GERENTE'],
    'configurar_alertas': ['SUPERVISOR', 'IT'],
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
