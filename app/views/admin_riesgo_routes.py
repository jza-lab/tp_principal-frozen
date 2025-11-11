from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required
from app.controllers.riesgo_controller import RiesgoController
from app.utils.decorators import permission_required

admin_riesgo_bp = Blueprint('admin_riesgo', __name__, url_prefix='/admin/riesgos')
from flask_jwt_extended import jwt_required, get_jwt_identity


@admin_riesgo_bp.route('/crear-alerta', methods=['POST'])
@jwt_required()
@permission_required(accion='gestionar_reclamos') # Reuse permission for now
def crear_alerta_riesgo_route():
    datos = request.json
    usuario_id = get_jwt_identity()

    controller = RiesgoController()
    response, status_code = controller.crear_alerta_riesgo_con_usuario(datos, usuario_id)

    if status_code == 201:
        alerta_codigo = response.get('data', {}).get('codigo')
        response['redirect_url'] = url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=alerta_codigo)
    
    return jsonify(response), status_code

@admin_riesgo_bp.route('/detalle/<codigo_alerta>')
@jwt_required()
@permission_required(accion='gestionar_reclamos')
def detalle_alerta_riesgo(codigo_alerta):
    controller = RiesgoController()
    response, status_code = controller.obtener_detalle_alerta_completo(codigo_alerta)
    
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
    usuario_id = get_jwt_identity()

    
    controller = RiesgoController()
    response, status_code = controller.ejecutar_accion_riesgo(codigo_alerta, form_data, usuario_id)

    return jsonify(response), status_code

@admin_riesgo_bp.route('/contactar-clientes/<codigo_alerta>', methods=['POST'])
@jwt_required()
@permission_required(accion='gestionar_reclamos')
def contactar_clientes(codigo_alerta):
    form_data = request.form
    controller = RiesgoController()
    response, status_code = controller.contactar_clientes_afectados(codigo_alerta, form_data)
    return jsonify(response), status_code

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


riesgos_bp = Blueprint('riesgos', __name__, url_prefix='/riesgos')

@riesgos_bp.route('/', methods=['GET'])
@permission_required('consultar_alertas_riesgo')
def listar_alertas_page():
    from app.controllers.usuario_controller import UsuarioController
    
    riesgo_controller = RiesgoController()
    usuario_controller = UsuarioController()
    
    resultado = riesgo_controller.alerta_riesgo_model.find_all()
    alertas = resultado.get('data', []) if resultado.get('success') else []
    # Enriquecer cada alerta con el nombre del usuario creador
    for alerta in alertas:
        if alerta.get('id_usuario_creador'):
            user_info = usuario_controller.obtener_detalles_completos_usuario(alerta['id_usuario_creador'])
            alerta['nombre_creador'] = user_info.get('nombre_completo', 'N/A') if user_info else 'N/A'
        else:
            alerta['nombre_creador'] = 'Sistema'
    return render_template('admin_riesgos/listado.html', alertas=alertas)

@riesgos_bp.route('/<codigo_alerta>', methods=['GET'])
@permission_required('consultar_alertas_riesgo')
def detalle_alerta_public_page(codigo_alerta):
    controller = RiesgoController()
    resultado,_ = controller.obtener_detalle_alerta_completo(codigo_alerta)
    if not resultado.get('success'):
        flash(resultado.get('error', 'Error desconocido'), 'danger')
        return redirect(url_for('riesgos.listar_alertas_page'))
    return render_template('admin_riesgos/detalle_publico.html', alerta=resultado.get('data'))

# API Endpoints
@riesgos_bp.route('/api/previsualizar', methods=['GET'])
@permission_required('crear_alerta_riesgo')
def api_previsualizar_riesgo():
    tipo_entidad = request.args.get('tipo_entidad')
    id_entidad = request.args.get('id_entidad')
    if not tipo_entidad or not id_entidad:
        return jsonify(success=False, error="tipo_entidad y id_entidad son requeridos."), 400
    
    controller = RiesgoController()
    resultado, status_code = controller.previsualizar_riesgo(tipo_entidad, id_entidad)
    return jsonify(resultado), status_code

@riesgos_bp.route('/api/crear', methods=['POST'])
@jwt_required()
@permission_required('crear_alerta_riesgo')
def api_crear_alerta_riesgo():
    usuario_id = get_jwt_identity()
    controller = RiesgoController()
    resultado, status_code = controller.crear_alerta_riesgo_con_usuario(request.json, usuario_id)
    
    if status_code == 201:
        alerta_codigo = resultado.get('data', {}).get('codigo')
        resultado['redirect_url'] = url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=alerta_codigo)
        
    return jsonify(resultado), status_code

@riesgos_bp.route('/api/subir_evidencia', methods=['POST'])
@permission_required('crear_alerta_riesgo')
def api_subir_evidencia():
    from app.controllers.storage_controller import StorageController
    import uuid
    

    if 'evidencia' not in request.files:
        return jsonify(success=False, error="No se encontró el archivo de evidencia."), 400
    
    file = request.files['evidencia']
    if file.filename == '':
        return jsonify(success=False, error="No se seleccionó ningún archivo."), 400

    # Crear un nombre de archivo único
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"evidencia_{uuid.uuid4()}.{file_extension}"

    
    controller = StorageController()
    resultado, status_code = controller.upload_file(file, 'evidencias_riesgos', unique_filename)

    return jsonify(resultado), status_code

@admin_riesgo_bp.route('/<string:codigo_alerta>/resolver', methods=['POST'])
@jwt_required(locations=["cookies"])
@permission_required('admin_riesgos')
def resolver_alerta_riesgo_manualmente(codigo_alerta):
    from app.controllers.riesgo_controller import RiesgoController
    from flask_jwt_extended import get_jwt_identity

    controller = RiesgoController()
    usuario_id = get_jwt_identity()
    resultado, status_code = controller.resolver_alerta_manualmente(codigo_alerta, usuario_id)

    if resultado.get('success'):
        flash(resultado.get('message', 'Alerta marcada como resuelta.'), 'success')
    else:
        flash(resultado.get('error', 'No se pudo resolver la alerta.'), 'danger')
        
    return redirect(url_for('admin_riesgo.detalle_alerta_riesgo', codigo_alerta=codigo_alerta))