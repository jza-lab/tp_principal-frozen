from flask import url_for

def get_redirect_url_by_role(role_code):
    """
    Devuelve la URL de redirección apropiada para un rol específico.
    Esta función centraliza la lógica de 'página de inicio' para cada rol.
    """
    # Siempre redirige al dashboard principal según el requerimiento.
    return url_for('admin_usuario.index')
