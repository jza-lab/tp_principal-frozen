from functools import wraps
from flask import session, flash, redirect, url_for
from app.models.permisos import PermisosModel
from app.models.sector import SectorModel
from app.models.usuario_sector import UsuarioSectorModel
from app.utils.roles import get_redirect_url_by_role
from app.utils.permission_map import get_allowed_roles_for_action

def permission_required(accion: str):
    """
    Decorator que verifica si un usuario tiene permiso para una acción.
    Utiliza el mapa canónico de permisos para determinar qué sectores pueden realizar la acción,
    y luego comprueba los permisos del usuario en sesión contra esa lista.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'usuario_id' not in session or 'rol_id' not in session or 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            # El Gerente General tiene acceso a todo
            if user_role_code == 'GERENTE_GENERAL':
                return f(*args, **kwargs)

            user_permissions = session.get('permisos', {})
            allowed_sectors = get_allowed_roles_for_action(accion)

            if not allowed_sectors:
                # Si la acción no está en el mapa, denegar por seguridad.
                flash(f'Acceso denegado. La acción "{accion}" no está configurada.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            # Comprueba si el usuario tiene el permiso en CUALQUIERA de los sectores permitidos
            has_permission = any(
                sector in user_permissions and accion in user_permissions[sector]
                for sector in allowed_sectors
            )

            if not has_permission:
                flash(f'Su rol no tiene los permisos necesarios ({accion}) para acceder a esta sección.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_permission_any_of(*actions):
    """
    Decorator que verifica si el rol tiene al menos UNO de varios permisos en 'ADMINISTRACION'.
    Prioriza la verificación contra los permisos guardados en la sesión.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol_id' not in session or 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            if user_role_code == 'GERENTE_GENERAL':
                return f(*args, **kwargs)

            user_permissions = session.get('permisos', {})
            admin_permissions = user_permissions.get('ADMINISTRACION', [])
            
            has_any_permission = any(action in admin_permissions for action in actions)

            if not has_any_permission:
                # Fallback a la base de datos
                role_id = session.get('rol_id')
                sector_model = SectorModel()
                sector_result = sector_model.find_by_codigo('ADMINISTRACION')
                if not sector_result.get('success') or not sector_result.get('data'):
                    flash('Error de configuración: El sector "ADMINISTRACION" no existe.', 'error')
                    return redirect(get_redirect_url_by_role(user_role_code))
                admin_sector_id = sector_result['data']['id']

                permission_model = PermisosModel()
                db_has_any = any(permission_model.check_permission(role_id, admin_sector_id, action) for action in actions)
                
                if not db_has_any:
                    action_str = " o ".join(f'"{a}"' for a in actions)
                    flash(f'Su rol no tiene los permisos necesarios ({action_str}).', 'error')
                    return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_permission_required(accion: str):
    """
    Decorator que verifica un permiso específico en el sector 'ADMINISTRACION'.
    Prioriza la verificación contra los permisos guardados en la sesión.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol_id' not in session or 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            user_role_code = session.get('rol')
            if user_role_code == 'GERENTE_GENERAL':
                return f(*args, **kwargs)

            user_permissions = session.get('permisos', {})
            admin_permissions = user_permissions.get('ADMINISTRACION', [])

            if accion not in admin_permissions:
                # Fallback a la base de datos
                role_id = session.get('rol_id')
                sector_model = SectorModel()
                sector_result = sector_model.find_by_codigo('ADMINISTRACION')
                if not sector_result.get('success') or not sector_result.get('data'):
                    flash('Error de configuración: El sector "ADMINISTRACION" no existe.', 'error')
                    return redirect(get_redirect_url_by_role(user_role_code))
                admin_sector_id = sector_result['data']['id']
                
                permission_model = PermisosModel()
                if not permission_model.check_permission(role_id, admin_sector_id, accion):
                    flash(f'Su rol no tiene permisos para "{accion}".', 'error')
                    return redirect(get_redirect_url_by_role(user_role_code))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
