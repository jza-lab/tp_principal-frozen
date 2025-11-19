from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.controllers.rol_controller import RolController
from app.utils.decorators import permission_required

rol_bp = Blueprint('rol', __name__, url_prefix='/admin/roles')

@rol_bp.route('/')
@permission_required('admin_configuracion_sistema')
def listar():
    controller = RolController()
    response, _ = controller.get_all_roles()
    roles = response.get('data', [])
    return render_template('roles/listar.html', roles=roles)

@rol_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@permission_required('admin_configuracion_sistema')
def editar(id):
    controller = RolController()
    if request.method == 'POST':
        data = request.form.to_dict()
        data.pop('csrf_token', None) # Eliminar el token CSRF antes de pasarlo al controlador
        _, status_code = controller.update_rol(id, data)
        if status_code == 200:
            flash('Rol actualizado exitosamente.', 'success')
            return redirect(url_for('rol.listar'))
        else:
            flash('Error al actualizar el rol.', 'error')

    response, _ = controller.get_rol_by_id(id)
    rol = response.get('data')
    if not rol:
        flash('Rol no encontrado.', 'error')
        return redirect(url_for('rol.listar'))
        
    return render_template('roles/formulario.html', rol=rol)
