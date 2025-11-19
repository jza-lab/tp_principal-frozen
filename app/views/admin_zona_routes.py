from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.controllers.zona_controller import ZonaController

zona_bp = Blueprint('zonas', __name__, url_prefix='/admin/zonas')
zona_controller = ZonaController()

@zona_bp.route('/')
def listar_zonas():
    return redirect(url_for('envio.gestion_envios'))

@zona_bp.route('/nueva', methods=['GET', 'POST'])
def crear_zona():
    if request.method == 'POST':
        data = request.form.to_dict()
        response = zona_controller.crear_o_actualizar_zona(data)
        if response.get('success'):
            flash('Zona creada exitosamente.', 'success')
            return redirect(url_for('envio.gestion_envios'))
        else:
            flash(response.get('error', 'Ocurrió un error al crear la zona.'), 'danger')
    
    return render_template('zonas/formulario.html', is_new=True, zona=None)

@zona_bp.route('/editar/<int:zona_id>', methods=['GET', 'POST'])
def editar_zona(zona_id):
    if request.method == 'POST':
        data = request.form.to_dict()
        response = zona_controller.crear_o_actualizar_zona(data, zona_id=zona_id)
        if response.get('success'):
            flash('Zona actualizada exitosamente.', 'success')
            return redirect(url_for('envio.gestion_envios'))
        else:
            flash(response.get('error', 'Ocurrió un error al actualizar la zona.'), 'danger')
    
    response = zona_controller.obtener_zona_por_id(zona_id)
    zona = response.get('data') if response.get('success') else None
    return render_template('zonas/formulario.html', zona=zona, is_new=False)

@zona_bp.route('/eliminar/<int:zona_id>', methods=['POST'])
def eliminar_zona(zona_id):
    response = zona_controller.eliminar_zona(zona_id)
    if response.get('success'):
        flash('Zona eliminada exitosamente.', 'success')
    else:
        flash(response.get('error', 'No se pudo eliminar la zona.'), 'danger')
    return redirect(url_for('envio.gestion_envios'))
