from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.proveedor_controller import ProveedorController
from app.controllers.insumo_controller import InsumoController
from app.utils.decorators import roles_required
from datetime import datetime # Importación de datetime para manejar las fechas

orden_compra_bp = Blueprint('orden_compra', __name__, url_prefix='/compras')

controller = OrdenCompraController()
proveedor_controller = ProveedorController()
insumo_controller = InsumoController()

@orden_compra_bp.route('/')
def listar():
    """
    Muestra la lista de órdenes de compra.
    Permite filtrar por estado.
    """
    estado = request.args.get('estado')
    filtros = {'estado': estado} if estado else {}
    
    # CORRECCIÓN: Se cambió 'obtener_ordenes' por el nombre correcto del método 'get_all_ordenes'
    # NOTA IMPORTANTE: Para que esta línea funcione correctamente, debes asegurarte de que el método
    # 'get_all_ordenes' en tu controlador acepte 'filtros' como argumento y devuelva un
    # diccionario de respuesta y el código de estado (response, status_code).
    response, status_code = controller.get_all_ordenes(filtros)
    ordenes = []
    if response.get('success'):
        ordenes_data = response.get('data', [])
        # Ordenar: no rechazadas primero, luego rechazadas
        ordenes = sorted(ordenes_data, key=lambda x: x.get('estado') == 'RECHAZADA')
    else:
        flash(response.get('error', 'Error al cargar las órdenes de compra.'), 'error')
        
    titulo = f"Órdenes de Compra"
    if estado:
        titulo += f" (Estado: {estado.replace('_', ' ').title()})"
    else:
        titulo += " (Todas)"

    return render_template('ordenes_compra/listar.html', ordenes=ordenes, titulo=titulo)

@orden_compra_bp.route('/nueva', methods=['GET', 'POST'])
def nueva():
    if request.method == 'POST':
        usuario_id = session.get('usuario_id')
        resultado = controller.crear_orden(request.form, usuario_id)
        if resultado.get('success'):
            flash('Orden de compra creada exitosamente.', 'success')
            return redirect(url_for('orden_compra.listar'))
        else:
            flash(f"Error al crear la orden: {resultado.get('error', 'Error desconocido')}", 'error')
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()
    insumos_resp, _ = insumo_controller.obtener_insumos()

    proveedores = proveedores_resp.get('data', []) if proveedores_resp.get('success') else []
    insumos = insumos_resp.get('data', []) if insumos_resp.get('success') else []

    return render_template('ordenes_compra/formulario.html', 
                           proveedores=proveedores, 
                           insumos=insumos, 
                           today=today) 

@orden_compra_bp.route('/detalle/<int:id>')
def detalle(id):
    response_data, status_code = controller.get_orden(id)
    
    if response_data.get('success'):
        orden = response_data.get('data')
        return render_template('ordenes_compra/detalle.html', orden=orden)
    else:
        flash(response_data.get('error', 'Orden de compra no encontrada.'), 'error')
        return redirect(url_for('orden_compra.listar'))


@orden_compra_bp.route('/<int:id>/aprobar', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def aprobar(id):
    usuario_id = session.get('usuario_id')
    resultado = controller.aprobar_orden(id, usuario_id)
    if resultado.get('success'):
        flash('Orden de compra aprobada.', 'success')
    else:
        flash(f"Error al aprobar: {resultado.get('error', 'Error desconocido')}", 'error')
    return redirect(url_for('orden_compra.listar'))

@orden_compra_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def editar(id):
    if request.method == 'POST':
        resultado = controller.actualizar_orden(id, request.form)
        if resultado.get('success'):
            flash('Orden de compra actualizada exitosamente.', 'success')
            return redirect(url_for('orden_compra.detalle', id=id))
        else:
            flash(f"Error al actualizar la orden: {resultado.get('error', 'Error desconocido')}", 'error')
            # Redirect back to the edit page to show the error
            return redirect(url_for('orden_compra.editar', id=id))

    # GET request
    response_data, status_code = controller.get_orden(id)
    if not response_data.get('success'):
        flash('Error al cargar la orden para editar.', 'error')
        return redirect(url_for('orden_compra.listar'))
    
    orden = response_data.get('data')
    
    proveedores_resp, _ = proveedor_controller.obtener_proveedores_activos()
    insumos_resp, _ = insumo_controller.obtener_insumos()

    proveedores = proveedores_resp.get('data', [])
    insumos = insumos_resp.get('data', [])

    return render_template('ordenes_compra/formulario.html', orden=orden, proveedores=proveedores, insumos=insumos)

@orden_compra_bp.route('/<int:id>/rechazar', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def rechazar(id):
    motivo = request.form.get('motivo', 'No especificado')
    resultado = controller.rechazar_orden(id, motivo)
    if resultado.get('success'):
        flash('Orden de compra rechazada.', 'warning')
    else:
        flash(f"Error al rechazar: {resultado.get('error', 'Error desconocido')}", 'error')
    return redirect(url_for('orden_compra.listar'))

@orden_compra_bp.route('/<int:id>/marcar-en-transito', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def marcar_en_transito(id):
    resultado = controller.marcar_en_transito(id)
    if resultado.get('success'):
        flash('La orden de compra ha sido marcada como "En Tránsito".', 'info')
    else:
        flash(f"Error al actualizar el estado: {resultado.get('error', 'Error desconocido')}", 'error')
    return redirect(url_for('orden_compra.listar'))

@orden_compra_bp.route('/recepcion/<int:orden_id>', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE', 'OPERARIO')
def procesar_recepcion(orden_id):
    """
    Procesa el formulario de recepción de una orden de compra.
    """
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        flash('Su sesión ha expirado, por favor inicie sesión de nuevo.', 'error')
        return redirect(url_for('auth.login'))

    resultado = controller.procesar_recepcion(orden_id, request.form, usuario_id)
    if resultado.get('success'):
        flash('Recepción de la orden procesada exitosamente. Se crearon los lotes en inventario.', 'success')
    else:
        flash(f"Error al procesar la recepción: {resultado.get('error', 'Error desconocido')}", 'error')
    
    return redirect(url_for('orden_compra.detalle', id=orden_id))
