from venv import logger
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.pedido_controller import PedidoController
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
    from app.models.motivo_desperdicio_model import MotivoDesperdicioModel
    from app.models.motivo_desperdicio_lote_model import MotivoDesperdicioLoteModel

    controller = RiesgoController()
    response, status_code = controller.obtener_detalle_alerta_completo(codigo_alerta)
    
    if status_code != 200:
        flash(response.get('error', 'No se pudo cargar la alerta.'), 'danger')
        return redirect(url_for('admin_riesgo.listar_alertas_riesgo'))

    alerta = response.get('data')
    
    # Cargar motivos de desperdicio para el modal de resolución
    motivos_insumo = MotivoDesperdicioModel().find_all().get('data', [])
    motivos_producto = MotivoDesperdicioLoteModel().get_all().get('data', [])

    return render_template(
        'admin_riesgos/detalle.html', 
        alerta=alerta,
        motivos_insumo=motivos_insumo,
        motivos_producto=motivos_producto
    )

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

@api_riesgos_bp.route('/lote_producto/<string:lote_id>/pedidos_afectados', methods=['GET'])
@jwt_required(locations=["cookies"])
def obtener_pedidos_lote_producto(lote_id):
    from app.models.trazabilidad import TrazabilidadModel
    from app.models.pedido import PedidoModel

    try:
        trazabilidad_model = TrazabilidadModel()
        pedido_model = PedidoModel()
        
        # Usar el sistema de trazabilidad para encontrar todos los pedidos afectados
        afectados_res = trazabilidad_model.obtener_trazabilidad_unificada('lote_producto', lote_id, nivel='simple')
        
        pedidos_afectados = []
        if afectados_res and 'resumen' in afectados_res:
            for item in afectados_res['resumen'].get('destino', []):
                if item.get('tipo') == 'pedido':
                    pedidos_afectados.append(item)

        data = []
        if pedidos_afectados:
            # Obtener detalles completos de los pedidos, incluyendo cliente y cantidad reservada
            for p_afectado in pedidos_afectados:
                pedido_id = p_afectado['id']
                pedido_detalles_res, _ = PedidoController().obtener_pedido_por_id(pedido_id)

                if not pedido_detalles_res.get('success'): continue
                pedido_completo = pedido_detalles_res.get('data', {})

                # Encontrar la cantidad reservada específicamente de este lote
                cantidad_reservada = 0
                reservas_del_lote = pedido_model.db.table('reservas_productos') \
                    .select('cantidad_reservada') \
                    .eq('lote_producto_id', lote_id) \
                    .in_('pedido_item_id', [item['id'] for item in pedido_completo.get('items', [])]) \
                    .execute().data
                
                if reservas_del_lote:
                    cantidad_reservada = sum(r['cantidad_reservada'] for r in reservas_del_lote)

                if cantidad_reservada > 0:
                     data.append({
                        'pedido_id': pedido_completo.get('id'),
                        'pedido_codigo': pedido_completo.get('codigo', f"#{pedido_id}"),
                        'cliente_nombre': pedido_completo.get('cliente', {}).get('nombre', 'Desconocido'),
                        'cantidad_reservada': cantidad_reservada
                    })

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Error al obtener pedidos para lote de producto {lote_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': "Error interno al buscar pedidos afectados."}), 500
