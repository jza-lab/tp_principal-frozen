from flask import url_for

def get_redirect_url_by_role(role_code):
    """
    Devuelve la URL de redirección apropiada para un rol específico.
    Esta función centraliza la lógica de 'página de inicio' para cada rol.
    """
    if role_code == 'SUPERVISOR':
        # Redirige a la página principal de producción
        return url_for('orden_produccion.listar')
    elif role_code in ['GERENTE', 'RRHH', 'IT']:
        # Roles que van al panel de administración principal
        return url_for('admin_usuario.index')
    elif role_code == 'COMERCIAL':
        # Rol comercial va a la gestión de ventas
        return url_for('orden_venta.listar')
    elif role_code == 'CALIDAD':
        # Rol de calidad va al inventario de lotes de productos terminados
        return url_for('inventario_view.listar_lotes_producto')
    
    # Fallback para EMPLEADO y cualquier otro rol, a una página segura
    return url_for('insumos_api.obtener_insumos')