from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.inventario_controller import InventarioController
from app.utils.decorators import permission_required
from app.controllers.insumo_controller import InsumoController
from app.controllers.proveedor_controller import ProveedorController
from marshmallow import ValidationError
from datetime import date


inventario_view_bp = Blueprint('inventario_view', __name__, url_prefix='/inventario')


@inventario_view_bp.route('/')
@permission_required(accion='almacen_consulta_stock')
def listar_lotes():
    """
    Muestra la lista de todos los lotes en el inventario, ahora agrupados por insumo.
    """
    controller = InventarioController()
    # Primero, se recalcula y actualiza el stock en la base de datos.
    controller.inventario_model.calcular_y_actualizar_stock_general()
    
    # Ahora, se obtienen los datos ya actualizados.
    response_agrupado, status_code = controller.obtener_lotes_agrupados_para_vista()
    filtros = request.args.to_dict()
    response, status_code = controller.obtener_lotes_para_vista(filtros)
    insumos_agrupados = []
    if response_agrupado.get('success'):
        insumos_agrupados = response_agrupado.get('data', [])
    else:
        flash(response_agrupado.get('error', 'Error al cargar los lotes del inventario.'), 'error')

    # Mantener la lógica existente para los gráficos por ahora
    stock_resp, _ = controller.obtener_stock_consolidado()
    insumos_stock = []
    insumos_full_data = []
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

    return render_template('inventario/listar.html',
                           insumos=insumos_agrupados,
                           insumos_stock=insumos_stock,
                           insumos_full_data=insumos_full_data)

@inventario_view_bp.route('/lote/nuevo', methods=['GET', 'POST'])
@jwt_required()
@permission_required(accion='registrar_ingreso_de_materia_prima')
def nuevo_lote():
    """
    Gestiona la creación de un nuevo lote en el inventario.
    """
    controller = InventarioController()
    insumo_controller = InsumoController()
    proveedor_controller = ProveedorController()
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
    controller = InventarioController()
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


@inventario_view_bp.route('/lote/<id_lote>/cuarentena', methods=['POST'])
##@jwt_required()
##@permission_required(accion='almacen_gestion_stock') # O el permiso que corresponda
def poner_en_cuarentena(id_lote):
    controller = InventarioController() # <-- AÑADIDO AQUÍ
    try:
        motivo = request.form.get('motivo_cuarentena')
        cantidad = float(request.form.get('cantidad_cuarentena'))
    except (TypeError, ValueError):
        flash('La cantidad debe ser un número válido.', 'danger')
        return redirect(url_for('inventario_view.listar_lotes'))

    response, status_code = controller.poner_lote_en_cuarentena(id_lote, motivo, cantidad)

    if response.get('success'):
        flash(response.get('message', 'Lote en cuarentena.'), 'success')
    else:
        flash(response.get('error', 'Error al procesar la solicitud.'), 'danger')

    return redirect(url_for('inventario_view.listar_lotes'))


@inventario_view_bp.route('/lote/<id_lote>/liberar', methods=['POST'])
##@jwt_required()
##@permission_required(accion='almacen_gestion_stock') # O el permiso que corresponda
def liberar_cuarentena(id_lote):
    controller = InventarioController()
    try:
        cantidad = float(request.form.get('cantidad_a_liberar'))
    except (TypeError, ValueError):
        flash('La cantidad a liberar debe ser un número válido.', 'danger')
        return redirect(url_for('inventario_view.listar_lotes'))

    response, status_code = controller.liberar_lote_de_cuarentena(id_lote, cantidad)

    if response.get('success'):
        flash(response.get('message', 'Lote liberado.'), 'success')
    else:
        flash(response.get('error', 'Error al procesar la solicitud.'), 'danger')

    return redirect(url_for('inventario_view.listar_lotes'))


@inventario_view_bp.route('/lote/<id_lote>/editar', methods=['GET', 'POST'])
##@jwt_required()
##@permission_required(accion='almacen_gestion_stock') # O el permiso que corresponda
def editar_lote(id_lote):
    
    """
    Gestiona la edición de un lote de inventario existente.
    """
    controller = InventarioController()
    if request.method == 'POST':
        try:
            datos_formulario = request.form.to_dict()
            datos_formulario.pop('csrf_token', None)  # Se elimina el token antes de validar
            # Llama al método del controlador que ya existía
            response, status_code = controller.actualizar_lote_parcial(id_lote, datos_formulario)

            if response.get('success'):
                flash(response.get('message', 'Lote actualizado con éxito.'), 'success')
                return redirect(url_for('inventario_view.listar_lotes'))
            else:
                flash(response.get('error', 'Error al actualizar.'), 'danger')

        except ValidationError as e: # Captura errores de validación del schema
            for field, errors in e.messages.items():
                flash(f"Error en el campo '{field}': {', '.join(errors)}", 'danger')
        except Exception as e:
            flash(f"Ocurrió un error inesperado: {e}", 'danger')

    # Lógica GET (o si falla el POST): Obtener datos y mostrar formulario
    response, status_code = controller.obtener_lote_por_id(id_lote)

    if not response.get('success'):
        flash(response.get('error', 'Lote no encontrado.'), 'danger')
        return redirect(url_for('inventario_view.listar_lotes'))

    lote = response.get('data')

    return render_template('inventario/editar_lote.html', lote=lote)
# --- FIN DE LA CORRECCIÓN ---
@inventario_view_bp.route('/api/lote/<id_lote>/trazabilidad')
def api_trazabilidad_lote(id_lote):
    controller = InventarioController()
    response, status_code = controller.obtener_trazabilidad_lote(id_lote)
    return jsonify(response), status_code