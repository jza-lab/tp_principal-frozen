from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.controllers.planificacion_controller import PlanificacionController
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.utils.decorators import roles_required

planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')

# Instanciamos los controladores
planificacion_controller = PlanificacionController()
orden_produccion_controller = OrdenProduccionController()

@planificacion_bp.route('/', methods=['GET'])
@roles_required('SUPERVISOR', 'ADMIN')
def index():
    """
    Muestra la página de planificación con los pedidos pendientes agrupados por producto.
    """
    pedidos_agrupados = planificacion_controller.obtener_pedidos_para_planificar()
    return render_template('planificacion/index.html', pedidos_agrupados=pedidos_agrupados)

@planificacion_bp.route('/crear_orden', methods=['POST'])
@roles_required('SUPERVISOR', 'ADMIN')
def crear_orden():
    """
    Endpoint para consolidar pedidos y crear una orden de producción.
    """
    producto_id = request.form.get('producto_id', type=int)
    pedido_ids = request.form.getlist('pedido_ids', type=int)
    usuario_id = session.get('usuario_id')

    if not producto_id or not pedido_ids:
        flash('Datos incompletos para crear la orden.', 'error')
        return redirect(url_for('planificacion.index'))

    resultado = orden_produccion_controller.crear_orden_desde_planificacion(
        producto_id=producto_id,
        pedidos_ids=pedido_ids,
        usuario_id=usuario_id
    )

    if resultado.get('success'):
        flash('Orden de producción creada exitosamente.', 'success')
    else:
        flash(f"Error al crear la orden: {resultado.get('error')}", 'error')

    return redirect(url_for('planificacion.index'))