from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.riesgo_controller import RiesgoController
from app.utils.decorators import permission_required

admin_riesgo_bp = Blueprint('admin_riesgo', __name__, url_prefix='/administrar/riesgos')
api_riesgos_bp = Blueprint('api_riesgos', __name__, url_prefix='/api/riesgos')

@admin_riesgo_bp.route('/', methods=['GET'])
@jwt_required(locations=["cookies"])
@permission_required('riesgos_ver')
def listar_alertas_riesgo():
    from app.models.alerta_riesgo import AlertaRiesgoModel
    from app.controllers.usuario_controller import UsuarioController
    
    usuario_controller = UsuarioController()
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    filtros = request.args.to_dict()
    if 'page' in filtros:
        del filtros['page']

    resultado = AlertaRiesgoModel().get_all_paginated(page, per_page, filtros)
    
    alertas = resultado.get('data', [])
    for alerta in alertas:
        if alerta.get('id_usuario_creador'):
            user_info = usuario_controller.obtener_detalles_completos_usuario(alerta['id_usuario_creador'])
            alerta['nombre_creador'] = user_info.get('nombre_completo', 'N/A') if user_info else 'N/A'
        else:
            alerta['nombre_creador'] = 'Sistema'

    return render_template(
        'admin_riesgos/listado.html',
        alertas=alertas,
        page=page,
        per_page=per_page,
        total=resultado.get('total', 0),
        total_pages=resultado.get('total_pages', 0),
        filtros=filtros
    )

@admin_riesgo_bp.route('/detalle/<codigo_alerta>')
@jwt_required(locations=["cookies"])
@permission_required('riesgos_ver')
def detalle_alerta_riesgo(codigo_alerta):
    controller = RiesgoController()
    response, status_code = controller.obtener_detalle_alerta_completo(codigo_alerta)
    
    if status_code != 200:
        flash(response.get('error', 'No se pudo cargar la alerta.'), 'danger')
        return redirect(url_for('admin_riesgo.listar_alertas_riesgo'))

    alerta = response.get('data')
    return render_template('admin_riesgos/detalle.html', alerta=alerta)

@admin_riesgo_bp.route('/<string:codigo_alerta>/resolver', methods=['POST'])
@jwt_required(locations=["cookies"])
@permission_required('riesgos_resolver')
def resolver_alerta_riesgo_manualmente(codigo_alerta):
    controller = RiesgoController()
    usuario_id = get_jwt_identity()
    resultado, status_code = controller.resolver_alerta_manualmente(codigo_alerta, usuario_id)

    if resultado.get('success'):
        flash(resultado.get('message', 'Alerta marcada como resuelta.'), 'success')
    else:
        flash(resultado.get('error', 'No se pudo resolver la alerta.'), 'danger')
        
    return redirect(url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=codigo_alerta))

@admin_riesgo_bp.route('/<int:alerta_id>/finalizar-analisis', methods=['POST'])
@jwt_required(locations=["cookies"])
@permission_required('riesgos_resolver')
def finalizar_analisis(alerta_id):
    conclusion = request.form.get('conclusion')
    usuario_id = get_jwt_identity()

    if not conclusion:
        flash("La conclusión es obligatoria.", "danger")
        return redirect(request.referrer)
        
    controller = RiesgoController()
    resultado, status_code = controller.finalizar_analisis_alerta(alerta_id, conclusion, usuario_id)
    
    if resultado.get('success'):
        flash(resultado.get('message'), 'success')
    else:
        flash(resultado.get('error'), 'danger')

    # Reconstruir la URL del detalle para redirigir
    alerta_res = controller.alerta_riesgo_model.find_by_id(alerta_id)
    codigo_alerta = alerta_res.get('data', {}).get('codigo')
    if codigo_alerta:
        return redirect(url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=codigo_alerta))
    return redirect(url_for('admin_riesgo.listar_alertas_riesgo'))


# --- API Endpoints ---
@api_riesgos_bp.route('/previsualizar', methods=['GET'])
@jwt_required(locations=["cookies"])
@permission_required('riesgos_crear')
def api_previsualizar_riesgo():
    tipo_entidad = request.args.get('tipo_entidad')
    id_entidad = request.args.get('id_entidad')
    if not tipo_entidad or not id_entidad:
        return jsonify(success=False, error="tipo_entidad y id_entidad son requeridos."), 400
    controller = RiesgoController()
    resultado, status_code = controller.previsualizar_riesgo(tipo_entidad, id_entidad)
    return jsonify(resultado), status_code

@api_riesgos_bp.route('/crear', methods=['POST'])
@jwt_required(locations=["cookies"])
@permission_required('riesgos_crear')
def api_crear_alerta_riesgo():
    usuario_id = get_jwt_identity()
    controller = RiesgoController()
    resultado, status_code = controller.crear_alerta_riesgo_con_usuario(request.json, usuario_id)
    if status_code == 201:
        alerta_codigo = resultado.get('data', {}).get('codigo')
        resultado['redirect_url'] = url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=alerta_codigo)
    return jsonify(resultado), status_code

@api_riesgos_bp.route('/subir_evidencia', methods=['POST'])
@jwt_required(locations=["cookies"])
@permission_required('riesgos_crear')
def api_subir_evidencia():
    from app.controllers.storage_controller import StorageController
    import uuid
    if 'evidencia' not in request.files:
        return jsonify(success=False, error="No se encontró el archivo de evidencia."), 400
    file = request.files['evidencia']
    if file.filename == '':
        return jsonify(success=False, error="No se seleccionó ningún archivo."), 400
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"evidencia_{uuid.uuid4()}.{file_extension}"
    controller = StorageController()
    resultado, status_code = controller.upload_file(file, 'evidencias_riesgos', unique_filename)
    return jsonify(resultado), status_code

@api_riesgos_bp.route('/contactar-clientes/<codigo_alerta>', methods=['POST'])
@jwt_required(locations=["cookies"])
@permission_required('riesgos_resolver')
def contactar_clientes(codigo_alerta):
    form_data = request.form
    controller = RiesgoController()
    response, status_code = controller.contactar_clientes_afectados(codigo_alerta, form_data)
    return jsonify(response), status_code

@api_riesgos_bp.route('/<int:alerta_id>/accion', methods=['POST'])
@jwt_required(locations=["cookies"])
@permission_required('riesgos_resolver')
def ejecutar_accion_api(alerta_id):
    datos = request.json
    usuario_id = get_jwt_identity()
    controller = RiesgoController()
    resultado, status_code = controller.ejecutar_accion_riesgo_api(alerta_id, datos, usuario_id)
    return jsonify(resultado), status_code

@api_riesgos_bp.route('/lote_producto/<int:lote_id>/pedidos_afectados', methods=['GET'])
@jwt_required(locations=["cookies"])
def obtener_pedidos_lote_producto(lote_id):
    from app.models.reserva_producto import ReservaProductoModel
    try:
        reserva_model = ReservaProductoModel()
        reservas_res = reserva_model.db.table('reservas_productos')\
            .select('cantidad_reservada, pedido:pedidos(id, codigo, clientes(nombre))')\
            .eq('lote_producto_id', lote_id).execute()
        
        data = []
        if reservas_res.data:
            for r in reservas_res.data:
                pedido = r.get('pedido') or {}
                cliente = pedido.get('clientes') or {}
                data.append({
                    'pedido_id': pedido.get('id'),
                    'pedido_codigo': pedido.get('codigo') or f"#{pedido.get('id')}",
                    'cliente_nombre': cliente.get('nombre', 'Desconocido'),
                    'cantidad_reservada': r.get('cantidad_reservada', 0)
                })
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
