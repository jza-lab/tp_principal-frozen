from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required
from app.controllers.riesgo_controller import RiesgoController
from app.utils.decorators import permission_required

admin_riesgo_bp = Blueprint('admin_riesgo', __name__, url_prefix='/admin/riesgos')

@admin_riesgo_bp.route('/crear-alerta', methods=['POST'])
@jwt_required()
@permission_required(accion='gestionar_reclamos') # Reuse permission for now
def crear_alerta_riesgo_route():
    datos = request.json
    controller = RiesgoController()
    response, status_code = controller.crear_alerta_riesgo(datos)

    if status_code == 201:
        alerta_codigo = response.get('data', {}).get('codigo')
        response['redirect_url'] = url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=alerta_codigo)
    
    return jsonify(response), status_code

@admin_riesgo_bp.route('/detalle/<codigo_alerta>')
@jwt_required()
@permission_required(accion='gestionar_reclamos')
def detalle_alerta_riesgo(codigo_alerta):
    controller = RiesgoController()
    response, status_code = controller.obtener_detalle_alerta(codigo_alerta)
    
    if status_code != 200:
        flash(response.get('error', 'No se pudo cargar la alerta.'), 'danger')
        return redirect(url_for('main.index')) # Fallback a una página principal

    alerta = response.get('data')
    return render_template('admin_riesgos/detalle.html', alerta=alerta)

@admin_riesgo_bp.route('/ejecutar-accion/<codigo_alerta>', methods=['POST'])
@jwt_required()
@permission_required(accion='gestionar_reclamos')
def ejecutar_accion_riesgo(codigo_alerta):
    form_data = request.form
    accion = form_data.get('accion')
    
    controller = RiesgoController()
    response, status_code = controller.ejecutar_accion_riesgo(codigo_alerta, accion, form_data)

    if status_code >= 400:
        flash(response.get('error', 'Ocurrió un error al procesar la acción.'), 'danger')
        return redirect(url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=codigo_alerta))
    
    flash(response.get('message', 'Acción ejecutada con éxito.'), 'success')
    if response.get('redirect_url'):
        return redirect(response['redirect_url'])
    
    return redirect(url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=codigo_alerta))

@admin_riesgo_bp.route('/accion-resultado')
@jwt_required()
@permission_required(accion='gestionar_reclamos')
def accion_resultado():
    from app.controllers.nota_credito_controller import NotaCreditoController
    nc_ids = request.args.getlist('nc_ids', type=int)
    
    controller = NotaCreditoController()
    notas_credito = []
    for nc_id in nc_ids:
        resp, _ = controller.obtener_detalle_nc(nc_id)
        if resp.get('success'):
            notas_credito.append(resp['data'])
            
    return render_template('admin_riesgos/accion_resultado.html', notas_credito=notas_credito)
