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
    # Módulo de Finanzas
    'finanzas_ver_precios_costos': ['VENDEDOR', 'SUPERVISOR', 'GERENTE', 'DEV'],

    # Módulo de Administración
    'admin_gestion_sistema': ['ADMIN', 'GERENTE', 'DEV'],
    'admin_supervision': ['SUPERVISOR', 'ADMIN', 'GERENTE', 'DEV'],
    'admin_gestion_personal': ['RRHH', 'GERENTE', 'DEV'],
    'admin_configuracion_sistema': ['IT', 'GERENTE', 'DEV'],

    # Módulo de Almacenamiento
    'almacen_gestion_completa': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'almacen_ver_registrar': ['OPERARIO', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'almacen_consulta_stock': ['VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'almacen_ver_insumos': ['SUPERVISOR_CALIDAD', 'SUPERVISOR', 'GERENTE', 'DEV'],

    # Módulo de Producción
    'produccion_gestion_completa': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'produccion_ejecucion': ['OPERARIO', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'produccion_consulta': ['VENDEDOR', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'produccion_control_proceso': ['SUPERVISOR_CALIDAD', 'SUPERVISOR', 'GERENTE', 'DEV'],

    # Módulo de Logística
    'logistica_supervision': ['SUPERVISOR', 'GERENTE', 'DEV'],
    'logistica_recepcion_oc': ['ADMIN', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'logistica_gestion_oc_ov': ['VENDEDOR', 'SUPERVISOR', 'GERENTE', 'DEV'],

    # Módulo de Calidad
    'calidad_gestion_completa': ['SUPERVISOR_CALIDAD', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'calidad_control_completo': ['SUPERVISOR', 'SUPERVISOR_CALIDAD', 'GERENTE', 'DEV'],
    'calidad_registro_recepcion': ['ADMIN', 'SUPERVISOR_CALIDAD', 'SUPERVISOR', 'GERENTE', 'DEV'],
    'calidad_registro_basico': ['OPERARIO', 'ADMIN', 'SUPERVISOR_CALIDAD', 'SUPERVISOR', 'GERENTE', 'DEV'],
    
    # Permiso General - Acceso Total por Módulo (para el rol de Gerente)
    'dashboard_acceder': ['ADMIN', 'VENDEDOR', 'OPERARIO', 'SUPERVISOR', 'SUPERVISOR_CALIDAD', 'RRHH', 'GERENTE', 'IT', 'DEV'],
    'finanzas_acceso_total': ['GERENTE', 'DEV'],
    'admin_acceso_total': ['GERENTE', 'DEV'],
    'almacen_acceso_total': ['GERENTE', 'DEV'],
    'produccion_acceso_total': ['GERENTE', 'DEV'],
    'logistica_acceso_total': ['GERENTE', 'DEV'],
    'calidad_acceso_total': ['GERENTE', 'DEV'],
}

def get_allowed_roles_for_action(action_name: str) -> list:
    """
    Devuelve la lista de códigos de rol permitidos para una acción específica.
    """
    # El rol de Gerente tiene acceso a todo
    if 'GERENTE' not in CANONICAL_PERMISSION_MAP.get(action_name, []):
         if action_name.startswith(('finanzas_', 'admin_', 'almacen_', 'produccion_', 'logistica_', 'calidad_')):
             return CANONICAL_PERMISSION_MAP.get(action_name, []) + ['GERENTE']

    return CANONICAL_PERMISSION_MAP.get(action_name, [])
    
