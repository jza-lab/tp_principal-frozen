from flask import url_for

def get_redirect_url_by_role(role_code):
    """
    Devuelve la URL de redirección apropiada para un rol específico.
    Esta función centraliza la lógica de 'página de inicio' para cada rol.
    """
    if role_code == 'SUPERVISOR':
        return url_for('orden_produccion.listar')
    elif role_code in ['GERENTE', 'RRHH', 'IT', 'COMERCIAL']:
        return url_for('admin_usuario.index')
    elif role_code in ['EMPLEADO', 'CALIDAD']:
        return url_for('insumos_api.obtener_insumos')
    
    # Fallback para cualquier otro caso o rol no definido
    return url_for('admin_usuario.index')