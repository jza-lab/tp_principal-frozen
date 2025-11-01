from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.inventario_controller import InventarioController
from app.utils.decorators import permission_required
from flask_wtf import FlaskForm

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

@control_calidad_bp.route('/orden/<int:orden_id>', methods=['GET'])
@jwt_required()
@permission_required('realizar_control_de_calidad_insumos')
def inspeccionar_orden(orden_id):
    """
    Muestra la página de detalle para inspeccionar los insumos de una orden de compra.
    """
    orden_controller = OrdenCompraController()
    inventario_controller = InventarioController()
    csrf_form = FlaskForm()

    # 1. Obtener los detalles de la Orden de Compra
    orden_result, _ = orden_controller.get_orden(orden_id)
    if not orden_result.get('success'):
        flash('La orden de compra no fue encontrada.', 'danger')
        return redirect(url_for('control_calidad.listar_ordenes_para_inspeccion'))
    
    orden = orden_result['data']
    codigo_oc = orden.get('codigo_oc')

    # 2. Obtener los lotes de inventario asociados a esta OC que están 'EN REVISION'
    if not codigo_oc:
        flash('La orden no tiene un código válido para buscar sus lotes.', 'danger')
        lotes = []
    else:
        lotes_result = inventario_controller.inventario_model.get_all_lotes_for_view(
            filtros={'documento_ingreso': codigo_oc, 'estado': 'EN REVISION'}
        )
        if not lotes_result.get('success'):
            flash('Error al obtener los lotes de la orden.', 'danger')
            lotes = []
        else:
            lotes = lotes_result.get('data', [])

    # Estados estáticos para el desplegable de inspección
    estados_inspeccion = ["Óptimo", "Paquete dañado", "Paquete roto", "Contaminación visual", "Olor extraño", "Tacto anómalo"]

    return render_template('ordenes_compra/inspeccionar.html', orden=orden, lotes=lotes, estados_inspeccion=estados_inspeccion, csrf_form=csrf_form)

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
                return redirect(url_for('control_calidad.inspeccionar_orden', orden_id=orden_id))
        return redirect(url_for('control_calidad.listar_ordenes_para_inspeccion'))

    from app.controllers.control_calidad_insumo_controller import ControlCalidadInsumoController
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

    # Redirigir de vuelta a la página de inspección de la misma orden
    inventario_controller = InventarioController()
    lote_res, _ = inventario_controller.obtener_lote_por_id(lote_id)
    if lote_res.get('success'):
         # Extraer orden_id del lote para la redirección
        orden_id = cc_controller._extraer_oc_id_de_lote(lote_res.get('data'))
        if orden_id:
            return redirect(url_for('control_calidad.inspeccionar_orden', orden_id=orden_id))

    return redirect(url_for('control_calidad.listar_ordenes_para_inspeccion'))
