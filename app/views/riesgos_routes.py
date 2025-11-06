from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash
from app.controllers.riesgo_controller import RiesgoController
from app.utils.decorators import permission_required

riesgos_bp = Blueprint('riesgos', __name__, url_prefix='/riesgos')
admin_riesgos_bp = Blueprint('admin_riesgos', __name__, url_prefix='/admin/riesgos')

@riesgos_bp.route('/', methods=['GET'])
@permission_required('consultar_alertas_riesgo')
def listar_alertas_page():
    controller = RiesgoController()
    resultado = controller.alerta_riesgo_model.find_all()
    alertas = resultado.get('data', []) if resultado.get('success') else []
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

@admin_riesgos_bp.route('/<codigo_alerta>/detalle', methods=['GET'])
@permission_required('gestionar_alertas_riesgo')
def detalle_riesgo_page(codigo_alerta):
    controller = RiesgoController()
    resultado,_ = controller.obtener_detalle_alerta_completo(codigo_alerta)
    if not resultado.get('success'):
        flash(resultado.get('error', 'Error desconocido'), 'danger')
        return redirect(url_for('admin_dashboard.index'))
    return render_template('admin_riesgos/detalle.html', alerta=resultado.get('data'))

@admin_riesgos_bp.route('/<codigo_alerta>/ejecutar', methods=['POST'])
@permission_required('gestionar_alertas_riesgo')
def ejecutar_accion_riesgo(codigo_alerta):
    controller = RiesgoController()
    resultado = controller.ejecutar_accion_riesgo(codigo_alerta, request.form)
    if resultado.get('success'):
        flash(resultado.get('message'), 'success')
        return redirect(resultado.get('redirect_url', url_for('admin_riesgos.detalle_riesgo_page', codigo_alerta=codigo_alerta)))
    else:
        flash(resultado.get('error'), 'danger')
        return redirect(url_for('admin_riesgos.detalle_riesgo_page', codigo_alerta=codigo_alerta))

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
@permission_required('crear_alerta_riesgo')
def api_crear_alerta_riesgo():
    controller = RiesgoController()
    resultado, status_code = controller.crear_alerta_riesgo(request.json)
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
