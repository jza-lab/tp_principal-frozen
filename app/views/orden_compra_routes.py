from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.controllers.orden_compra_controller import OrdenCompraController, safe_serialize_simple
from app.utils.decorators import roles_required

orden_compra_bp = Blueprint('orden_compra', __name__, url_prefix='/compras')

controller = OrdenCompraController()

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
        ordenes = response.get('data', [])
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
    
    return render_template('ordenes_compra/formulario.html')

@orden_compra_bp.route('/detalle/<int:id>')
def detalle(id):
    response = controller.get_orden(id) 
    data = response.get_json()          
    orden = data.get('data') if data else None
    
    if not orden:
        flash(data.get('error', 'Orden de compra no encontrada.'), 'error')
        return redirect(url_for('orden_compra.listar'))

    return render_template('ordenes_compra/detalle.html', orden=orden)


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
