from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.controllers.orden_produccion_controller import OrdenProduccionController
# from app.controllers.etapa_produccion_controller import EtapaProduccionController
from app.utils.decorators import roles_required
from datetime import date

orden_produccion_bp = Blueprint('orden_produccion', __name__, url_prefix='/ordenes')

# Se instancian los controladores necesarios
controller = OrdenProduccionController()
# etapa_controller = EtapaProduccionController()

@orden_produccion_bp.route('/')
def listar():
    """
    Muestra la lista de órdenes de producción.
    Permite filtrar por estado.
    """
    estado = request.args.get('estado')
    filtros = {'estado': estado} if estado else {}
    ordenes = controller.obtener_ordenes(filtros)
    return render_template('ordenes_produccion/listar.html', ordenes=ordenes)

# @orden_produccion_bp.route('/nueva', methods=['GET', 'POST'])
# def nueva():
#     """
#     Gestiona la creación de una nueva orden de producción a través de un formulario.
#     DESHABILITADO: Las órdenes de producción ahora se deben generar desde el
#     módulo de planificación, consolidando los pedidos de clientes.
#     """
#
#     # Redirigir siempre a la lista con un mensaje informativo.
#     flash('La creación directa de órdenes está deshabilitada. Use el módulo de Planificación.', 'info')
#     return redirect(url_for('orden_produccion.listar'))

@orden_produccion_bp.route('/<int:id>')
def detalle(id):
    """
    Muestra la página de detalle de una orden de producción específica,
    incluyendo sus etapas.
    """
    orden = controller.obtener_orden_por_id(id)
    if not orden:
        flash('Orden no encontrada.', 'error')
        return redirect(url_for('orden_produccion.listar'))

    # etapas = etapa_controller.obtener_etapas_por_orden(id)

    # return render_template('ordenes_produccion/detalle.html', orden=orden, etapas=etapas)
    return render_template('ordenes_produccion/detalle.html', orden=orden, etapas=etapas)

@orden_produccion_bp.route('/<int:id>/iniciar', methods=['POST'])
def iniciar(id):
    """
    Endpoint para cambiar el estado de una orden a 'EN_PROCESO'.
    """
    resultado = controller.cambiar_estado_orden(id, 'EN_PROCESO')
    if resultado.get('success'):
        flash('Orden iniciada exitosamente.', 'success')
    else:
        flash(f"Error al iniciar la orden: {resultado.get('error', 'Error desconocido')}", 'error')

    return redirect(url_for('orden_produccion.detalle', id=id))

@orden_produccion_bp.route('/<int:id>/completar', methods=['POST'])
def completar(id):
    """
    Endpoint para cambiar el estado de una orden a 'COMPLETADA'.
    """
    resultado = controller.cambiar_estado_orden(id, 'COMPLETADA')
    if resultado.get('success'):
        flash('Orden completada exitosamente.', 'success')
    else:
        flash(f"Error al completar la orden: {resultado.get('error', 'Error desconocido')}", 'error')

    return redirect(url_for('orden_produccion.detalle', id=id))

@orden_produccion_bp.route('/pendientes')
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def listar_pendientes():
    """
    Muestra las órdenes de producción pendientes de aprobación para el supervisor.
    """
    ordenes = controller.obtener_ordenes({'estado': 'PENDIENTE'})
    return render_template('ordenes_produccion/pendientes.html', ordenes=ordenes)

@orden_produccion_bp.route('/<int:id>/aprobar', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def aprobar(id):
    """
    Endpoint para que el supervisor apruebe una orden.
    """
    usuario_id = session.get('usuario_id') # Asumimos que el ID del supervisor es necesario
    resultado = controller.aprobar_orden(id, usuario_id)
    if resultado.get('success'):
        flash('Orden aprobada y stock reservado.', 'success')
    else:
        flash(f"Error al aprobar: {resultado.get('error', 'Error desconocido')}", 'error')
    return redirect(url_for('orden_produccion.listar_pendientes'))

@orden_produccion_bp.route('/<int:id>/rechazar', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN', 'GERENTE')
def rechazar(id):
    """
    Endpoint para que el supervisor rechace una orden.
    """
    motivo = request.form.get('motivo', 'No especificado')
    resultado = controller.rechazar_orden(id, motivo)
    if resultado.get('success'):
        flash('Orden rechazada exitosamente.', 'warning')
    else:
        flash(f"Error al rechazar: {resultado.get('error', 'Error desconocido')}", 'error')
    return redirect(url_for('orden_produccion.listar_pendientes'))