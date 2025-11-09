from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.inventario_controller import InventarioController
from app.utils.decorators import permission_required
from flask_wtf import FlaskForm
from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController

control_calidad_bp = Blueprint('control_calidad', __name__, url_prefix='/control-calidad')

@control_calidad_bp.route('/ordenes', methods=['GET'])
@jwt_required()
@permission_required('realizar_control_de_calidad_insumos')
def listar_ordenes_para_inspeccion():
    """
    Muestra una lista de órdenes de compra que están en estado 'EN_CONTROL_CALIDAD'.
    """
    orden_controller = OrdenCompraController()
    ordenes_result, status_code = orden_controller.get_all_ordenes(filtros={'estado': 'EN_CONTROL_CALIDAD'})
    
    if not ordenes_result.get('success'):
        flash(ordenes_result.get('error', 'Error al obtener las órdenes.'), 'danger')
        ordenes = []
    else:
        ordenes = ordenes_result.get('data', [])
        
    return render_template('ordenes_compra/listar.html', ordenes=ordenes)

@control_calidad_bp.route('/lote/<string:lote_id>/procesar', methods=['POST'])
@jwt_required()
@permission_required('realizar_control_de_calidad_insumos')
def procesar_inspeccion(lote_id):
    """
    Procesa el formulario de inspección para un lote de insumo.
    """
    user_id = get_jwt_identity()
    form_data = request.form
    foto_file = request.files.get('foto')
    decision = form_data.get('decision')

    if not decision:
        flash('No se ha tomado una decisión. Por favor, inténtelo de nuevo.', 'danger')
        # Necesitamos la orden_id para redirigir, la recuperaremos del lote
        inventario_controller = InventarioController()
        lote_res, _ = inventario_controller.obtener_lote_por_id(lote_id)
        if lote_res.get('success'):
            orden_id = lote_res['data'].get('orden_compra_id') # Asumiendo que la tenemos aquí
            if orden_id:
                return redirect(url_for('orden_compra.detalle', id=orden_id))
        return redirect(url_for('control_calidad.listar_ordenes_para_inspeccion'))

    cc_controller = ControlCalidadInsumoController()
    
    resultado, status_code = cc_controller.procesar_inspeccion(
        lote_id=lote_id,
        decision=decision,
        form_data=form_data,
        foto_file=foto_file,
        usuario_id=user_id
    )

    if resultado.get('success'):
        flash(resultado.get('message', 'Inspección procesada con éxito.'), 'success')
    else:
        flash(resultado.get('error', 'Ocurrió un error al procesar la inspección.'), 'danger')

    # Corrección: Redirigir a la lista general de órdenes de compra para evitar el filtro "CERRADA"
    return redirect(url_for('orden_compra.listar'))

@control_calidad_bp.route('/api/lote/<string:lote_id>/<string:accion>', methods=['POST'])
@jwt_required()
@permission_required('realizar_control_de_calidad_insumos')
def procesar_inspeccion_api(lote_id, accion):
    """
    API para procesar la inspección de un lote (Aceptar, Poner en Cuarentena, Rechazar).
    """
    user_id = get_jwt_identity()
    
    # Para 'Aceptar', no esperamos un cuerpo JSON.
    if accion == 'aceptar':
        form_data = {}
        foto_file = None
        decision = 'Aceptar'
    else:
        # Para 'cuarentena' y 'rechazar', esperamos datos de formulario multipart/form-data
        # ya que puede incluir una foto.
        form_data = request.form
        foto_file = request.files.get('foto')
        if accion == 'cuarentena':
            decision = 'Poner en Cuarentena'
        elif accion == 'rechazar':
            decision = 'Rechazar'
        else:
            return jsonify({'success': False, 'error': 'Acción no válida.'}), 400

    cc_controller = ControlCalidadInsumoController()
    
    resultado, status_code = cc_controller.procesar_inspeccion_api(
        lote_id=lote_id,
        decision=decision,
        form_data=form_data,
        foto_file=foto_file,
        usuario_id=user_id
    )
    
    return jsonify(resultado), status_code

@control_calidad_bp.route('/api/orden/<int:orden_id>/finalizar', methods=['POST'])
@jwt_required()
@permission_required('realizar_control_de_calidad_insumos')
def finalizar_inspeccion_api(orden_id):
    """
    API para marcar una orden como 'CERRADA' después de la inspección.
    """
    usuario_id = get_jwt_identity()
    cc_controller = ControlCalidadInsumoController()
    resultado, status_code = cc_controller.finalizar_inspeccion_orden(orden_id, usuario_id)
    
    return jsonify(resultado), status_code
