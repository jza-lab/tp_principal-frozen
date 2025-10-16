from flask import url_for

def get_redirect_url_by_role(role_code: str) -> str:
    """
    Determina la URL de redirección post-login basada en el código del rol.

    Actualmente, todos los roles son redirigidos al dashboard principal.
    Esta función centraliza la lógica para facilitar futuros cambios si se
    requieren dashboards específicos por rol.
    """
    
    # En la arquitectura actual, el dashboard es el punto de entrada para todos los roles.
    # Se corrige el endpoint para que apunte al nuevo blueprint del dashboard.
    return url_for('admin_dashboard.index')
