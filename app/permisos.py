from functools import wraps
from flask import session, flash, redirect, url_for
from app.models.permisos import PermisosModel
from app.models.sector import SectorModel
from app.models.usuario_sector import UsuarioSectorModel
from app.utils.roles import get_redirect_url_by_role

def permission_required(sector_codigo: str, accion: str):
    """
    Decorator que verifica si un usuario tiene permiso para una acción en un sector.
    Realiza una doble verificación:
    1. El ROL del usuario tiene el permiso para esa acción en ese sector.
    2. El USUARIO específico está asignado a ese sector.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Verificar login básico
            if 'usuario_id' not in session or 'rol_id' not in session or 'rol' not in session:
                flash('Acceso no autorizado. Por favor, inicie sesión.', 'error')
                return redirect(url_for('auth.login'))

            # 2. Obtener datos de la sesión
            usuario_id = session.get('usuario_id')
            role_id = session.get('rol_id')
            user_role_code = session.get('rol')

            # 3. Acceso universal para GERENTE
            if user_role_code == 'GERENTE':
                return f(*args, **kwargs)

            # 4. Obtener ID del sector
            sector_model = SectorModel()
            sector_result = sector_model.find_by_codigo(sector_codigo)
            if not sector_result.get('success') or not sector_result.get('data'):
                flash(f'Error de configuración: El sector "{sector_codigo}" no existe.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))
            sector_id = sector_result['data']['id']

            # 5. VERIFICACIÓN DE PERMISO DEL ROL
            permission_model = PermisosModel()
            rol_tiene_permiso = permission_model.check_permission(role_id, sector_id, accion)
            if not rol_tiene_permiso:
                flash(f'Su rol no tiene permisos para "{accion}" en el sector de {sector_codigo}.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            # 6. VERIFICACIÓN DE ASIGNACIÓN DEL USUARIO AL SECTOR
            usuario_sector_model = UsuarioSectorModel()
            usuario_asignado_al_sector = usuario_sector_model.check_user_sector_assignment(usuario_id, sector_id)
            if not usuario_asignado_al_sector:
                flash(f'No tiene acceso al sector de {sector_codigo}. Contacte a un administrador.', 'error')
                return redirect(get_redirect_url_by_role(user_role_code))

            # 7. Si ambas verificaciones pasan, continuar.
            return f(*args, **kwargs)
        return decorated_function
    return decorator