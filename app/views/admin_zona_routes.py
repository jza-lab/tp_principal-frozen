from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.controllers.zona_controller import ZonaController
import json
# from app.utils.decorators import permission_required

zona_bp = Blueprint('zonas', __name__, url_prefix='/admin/zonas')
zona_controller = ZonaController()

@zona_bp.route('/')
# @permission_required('consultar_zonas')
def listar_zonas():
    return redirect(url_for('envio.gestion_envios'))

@zona_bp.route('/nueva', methods=['GET', 'POST'])
# @permission_required('crear_zonas')
def crear_zona():
    if request.method == 'POST':
        data = request.form.to_dict()
        data['localidades_ids'] = json.loads(data.get('localidades_ids', '[]'))
        response = zona_controller.crear_o_actualizar_zona(data)
        if response['success']:
            flash('Zona creada exitosamente.', 'success')
            return redirect(url_for('envio.gestion_envios'))
        else:
            flash(response.get('error', 'Ocurrió un error.'), 'danger')
    
    return render_template('zonas/formulario.html', is_new=True, zona=None)

@zona_bp.route('/editar/<int:zona_id>', methods=['GET', 'POST'])
# @permission_required('modificar_zonas')
def editar_zona(zona_id):
    if request.method == 'POST':
        data = request.form.to_dict()
        data['localidades_ids'] = json.loads(data.get('localidades_ids', '[]'))
        response = zona_controller.crear_o_actualizar_zona(data, zona_id=zona_id)
        if response['success']:
            flash('Zona actualizada exitosamente.', 'success')
            return redirect(url_for('envio.gestion_envios'))
        else:
            flash(response.get('error', 'Ocurrió un error.'), 'danger')
    
    response = zona_controller.obtener_zona_por_id(zona_id)
    zona = response.get('data')
    return render_template('zonas/formulario.html', zona=zona, is_new=False)

@zona_bp.route('/eliminar/<int:zona_id>', methods=['POST'])
# @permission_required('eliminar_zonas')
def eliminar_zona(zona_id):
    response = zona_controller.eliminar_zona(zona_id)
    if response['success']:
        flash('Zona eliminada exitosamente.', 'success')
    else:
        flash(response.get('error', 'No se pudo eliminar la zona.'), 'danger')
    return redirect(url_for('envio.gestion_envios'))

@zona_bp.route('/api/buscar-localidades')
# @permission_required('consultar_zonas')
def api_buscar_localidades():
    term = request.args.get('term', '')
    response = zona_controller.buscar_localidades(term)
    if response['success']:
        return jsonify(response['data'])
    return jsonify([])
