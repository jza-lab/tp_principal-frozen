from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.controllers.inventario_controller import InventarioController
from app.utils.decorators import permission_required
from app.controllers.insumo_controller import InsumoController
from app.controllers.proveedor_controller import ProveedorController
from app.models.motivo_desperdicio_model import MotivoDesperdicioModel
from marshmallow import ValidationError
from datetime import date, datetime
from app.utils.estados import ESTADOS_INSPECCION


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

    # Cargar motivos de desperdicio para el modal de No Apto
    motivo_model = MotivoDesperdicioModel()
    motivos_res = motivo_model.find_all()
    motivos_desperdicio = motivos_res.get('data', []) if motivos_res.get('success') else []

    return render_template('inventario/listar.html',
                           insumos=insumos_agrupados,
                           insumos_stock=insumos_stock,
                           insumos_full_data=insumos_full_data,
                           estados_inspeccion=ESTADOS_INSPECCION,
                           motivos_desperdicio=motivos_desperdicio)

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

    insumos = insumos_resp.get('data', [])
    today = date.today().isoformat()

    # Ahora enriquecemos cada insumo con los datos de su proveedor
    proveedor_controller = ProveedorController()
    proveedores_cache = {}

    insumos_enriquecidos = []
    for insumo in insumos:
        proveedor_id = insumo.get('id_proveedor')
        if proveedor_id:
            if proveedor_id not in proveedores_cache:
                prov_resp, _ = proveedor_controller.obtener_proveedor(proveedor_id)
                if prov_resp.get('success'):
                    proveedores_cache[proveedor_id] = prov_resp.get('data')
            
            insumo['proveedor'] = proveedores_cache.get(proveedor_id)
            insumos_enriquecidos.append(insumo)

    return render_template('inventario/formulario.html',
                           insumos=insumos_enriquecidos,
                           today=today)

@inventario_view_bp.route('/lote/<id_lote>')
@permission_required(accion='almacen_consulta_stock')
def detalle_lote(id_lote):
    """
    Muestra la página de detalle para un lote específico.
    """
    controller = InventarioController()
    response, status_code = controller.obtener_lote_por_id(id_lote)

    if response.get('success'):
        lote = response.get('data')
        
        # Convertir las fechas del historial de calidad a objetos datetime
        if lote.get('historial_calidad'):
            for evento in lote['historial_calidad']:
                if evento.get('created_at'):
                    try:
                        # Eliminar la 'Z' y cualquier cosa después del punto si existe
                        date_string = evento['created_at'].split('.')[0].replace('Z', '')
                        evento['created_at'] = datetime.fromisoformat(date_string)
                    except (ValueError, TypeError):
                        # Si hay un error, simplemente dejar la cadena como está
                        pass

        return render_template('inventario/detalle.html', lote=lote)
    else:
        flash(response.get('error', 'Lote no encontrado.'), 'error')
        return redirect(url_for('inventario_view.listar_lotes'))


@inventario_view_bp.route('/lote/<id_lote>/cuarentena', methods=['POST'])
@jwt_required()
@permission_required(accion='almacen_consulta_stock') # O el permiso que corresponda
def poner_en_cuarentena(id_lote):
    controller = InventarioController()
    try:
        motivo = request.form.get('motivo_cuarentena')
        cantidad = float(request.form.get('cantidad_cuarentena'))
        usuario_id = get_jwt_identity()
        resultado_inspeccion = request.form.get('resultado_inspeccion')
        foto_file = request.files.get('foto')
    except (TypeError, ValueError):
        flash('La cantidad debe ser un número válido.', 'danger')
        return redirect(url_for('inventario_view.listar_lotes'))

    response, status_code = controller.poner_lote_en_cuarentena(
        lote_id=id_lote,
        motivo=motivo,
        cantidad=cantidad,
        usuario_id=usuario_id,
        resultado_inspeccion=resultado_inspeccion,
        foto_file=foto_file
    )

    if response.get('success'):
        flash(response.get('message', 'Lote en cuarentena.'), 'success')
    else:
        flash(response.get('error', 'Error al procesar la solicitud.'), 'danger')

    return redirect(url_for('inventario_view.listar_lotes'))


@inventario_view_bp.route('/lote/<id_lote>/liberar', methods=['POST'])
@jwt_required()
@permission_required(accion='almacen_consulta_stock') # O el permiso que corresponda
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
@jwt_required()
@permission_required(accion='almacen_consulta_stock') # O el permiso que corresponda
def editar_lote(id_lote):
    
    """
    Gestiona la edición de un lote de inventario existente.
    """
    controller = InventarioController()
    if request.method == 'POST':
        try:
            datos_formulario = request.form.to_dict()
            datos_formulario.pop('csrf_token', None)

            # Validación manual de Backend para el precio
            if datos_formulario.get('precio_unitario'):
                try:
                    precio = float(datos_formulario['precio_unitario'])
                    if not (0 <= precio <= 999999999.99):
                        flash('El precio unitario excede el límite permitido (máx 999,999,999.99).', 'danger')
                        return redirect(url_for('inventario_view.editar_lote', id_lote=id_lote))
                except (ValueError, TypeError):
                    flash('El precio unitario debe ser un número válido.', 'danger')
                    return redirect(url_for('inventario_view.editar_lote', id_lote=id_lote))

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

@inventario_view_bp.route('/lote/<lote_id>/marcar-no-apto', methods=['POST','PUT'])
@jwt_required()
@permission_required('realizar_control_de_calidad_insumos')
def marcar_no_apto(lote_id):
    """
    Marca un lote de insumo como 'NO APTO' y maneja las consecuencias.
    Soporta retiro con desperdicio o creación de alerta.
    """
    controller = InventarioController()
    usuario_id = get_jwt_identity()
    
    # Extraer datos del formulario (maneja el nuevo modal complejo)
    accion = request.form.get('accion_no_apto') # 'retirar' o 'alerta'
    
    if accion:
        # Nuevo flujo: Pasamos también request.files para manejar la imagen
        foto_file = request.files.get('foto_no_apto')
        response, status_code = controller.procesar_no_apto_avanzado(lote_id, request.form, usuario_id, foto_file)
    else:
        # Flujo legacy (por si acaso)
        response, status_code = controller.marcar_lote_como_no_apto(lote_id, usuario_id)

    if response.get('success'):
        flash(response.get('message', 'Acción realizada correctamente.'), 'success')
    else:
        flash(response.get('error', 'Error al procesar la solicitud.'), 'danger')

    return redirect(url_for('inventario_view.listar_lotes'))

@inventario_view_bp.route('/api/lote/<lote_id>/ops_afectadas')
@jwt_required()
def obtener_ops_afectadas(lote_id):
    """
    Devuelve las Órdenes de Producción que tienen reservado stock de este lote.
    """
    from app.models.reserva_insumo import ReservaInsumoModel
    from app.models.orden_produccion import OrdenProduccionModel
    
    reserva_model = ReservaInsumoModel()
    op_model = OrdenProduccionModel()
    
    try:
        # Buscar reservas
        reservas = reserva_model.find_all(filters={'lote_inventario_id': lote_id}).get('data', [])
        
        if not reservas:
            return jsonify({'success': True, 'data': []}), 200
            
        op_ids = list(set(r['orden_produccion_id'] for r in reservas))
        
        # Buscar detalles de las OPs
        ops_data = []
        if op_ids:
            ops_res = op_model.find_all(filters={'id': ('in', op_ids)})
            if ops_res.get('success'):
                # Filtrar solo OPs activas (Case Insensitive)
                ops_data = [
                    {
                        'id': op['id'], 
                        'codigo': op.get('codigo', f"ID {op['id']}"),
                        'estado': op.get('estado')
                    } 
                    for op in ops_res['data'] 
                    if str(op.get('estado', '')).upper() not in ['COMPLETADA', 'FINALIZADA', 'CANCELADA', 'RECHAZADA', 'CONSOLIDADA']
                ]
        
        return jsonify({'success': True, 'data': ops_data}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500