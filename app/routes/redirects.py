from flask import Blueprint, redirect, url_for

# Este blueprint es para manejar redirecciones de URLs antiguas o incorrectas.
redirect_bp = Blueprint('redirects', __name__)

@redirect_bp.route('/usuarios/totem')
def redirect_old_totem():
    """
    Redirige la URL antigua /usuarios/totem a la nueva y correcta /totem/.
    Esto soluciona el problema de los enlaces rotos de forma permanente.
    El código 301 indica a los navegadores que la redirección es permanente.
    """
    return redirect(url_for('totem.totem_handler'), code=301)