from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.inventario_controller import InventarioController
from app.utils.decorators import permission_required
from app.controllers.insumo_controller import InsumoController
from app.controllers.proveedor_controller import ProveedorController
from marshmallow import ValidationError
from datetime import date


inventario_view_bp = Blueprint('inventario_view', __name__, url_prefix='/inventario')
controller = InventarioController()
insumo_controller = InsumoController()
proveedor_controller = ProveedorController()

@inventario_view_bp.route('/')
@permission_required(accion='almacen_consulta_stock')
def listar_lotes():
    """
    Muestra la lista de todos los lotes en el inventario.
    """
    filtros = request.args.to_dict()
    response, status_code = controller.obtener_lotes_para_vista(filtros)
    
    lotes = []
    if response.get('success'):
        lotes = response.get('data', [])
    else:
        flash(response.get('error', 'Error al cargar los lotes del inventario.'), 'error')
    
    stock_resp, _ = controller.obtener_stock_consolidado()
    insumos_stock = []
    if stock_resp.get('success'):

        insumos_data = stock_resp.get('data', [])
        insumos_stock = [
            i for i in insumos_data
            if float(i.get('stock_actual') or 0.0) > 0.0 
        ]

        insumos_stock.sort(key=lambda x: (
            1 if x.get('estado_stock') == 'OK' else 0, 
            float(x.get('stock_actual') or 0.0) * -1
        ))
        insumos_full_data = insumos_data
        
    return render_template('inventario/listar.html', lotes=lotes, insumos_stock=insumos_stock, insumos_full_data=insumos_full_data)

@inventario_view_bp.route('/lote/nuevo', methods=['GET', 'POST'])
@jwt_required()
@permission_required(accion='registrar_ingreso_de_materia_prima')
def nuevo_lote():
    """
    Gestiona la creación de un nuevo lote en el inventario.
    """
    if request.method == 'POST':
        try:
            usuario_id = get_jwt_identity()
            response, status_code = controller.crear_lote(request.form.to_dict(), usuario_id)

            if response.get('success'):
                flash('Lote registrado en el inventario exitosamente.', 'success')
                return redirect(url_for('inventario_view.listar_lotes'))
            else:
                flash(f"Error al registrar el lote: {response.get('error', 'Error desconocido')}", 'error')

        except ValidationError as e:
            for field, errors in e.messages.items():
                for error in errors:
                    flash(f"Error en el campo '{field}': {error}", 'error')
        except Exception as e:
            flash(f"Ocurrió un error inesperado: {e}", 'error')

    insumos_resp, _ = insumo_controller.obtener_insumos({'activo': True})
    proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()

    insumos = insumos_resp.get('data', [])
    proveedores = proveedores_resp.get('data', [])
    today = date.today().isoformat()

    return render_template('inventario/formulario.html', 
                           insumos=insumos, 
                           proveedores=proveedores, 
                           today=today)

@inventario_view_bp.route('/lote/<id_lote>')
@permission_required(accion='consultar_stock')
def detalle_lote(id_lote):
    """
    Muestra la página de detalle para un lote específico.
    """
    response, status_code = controller.obtener_lote_por_id(id_lote)
    
    if response.get('success'):
        lote = response.get('data')
        insumo_resp = controller.insumo_model.find_by_id(lote.get('id_insumo'), 'id_insumo')
        if insumo_resp.get('success'):
            lote['insumo_nombre'] = insumo_resp['data'].get('nombre')
            lote['insumo_unidad_medida'] = insumo_resp['data'].get('unidad_medida')
        
        return render_template('inventario/detalle.html', lote=lote)
    else:
        flash(response.get('error', 'Lote no encontrado.'), 'error')
        return redirect(url_for('inventario_view.listar_lotes'))
