from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.controllers.orden_produccion_controller import OrdenProduccionController
from app.models.pedido import PedidoModel
from app.utils.decorators import roles_required
from itertools import groupby
from operator import itemgetter

planificacion_bp = Blueprint('planificacion', __name__, url_prefix='/planificacion')

orden_produccion_controller = OrdenProduccionController()
pedido_model = PedidoModel()

@planificacion_bp.route('/')
@roles_required(min_level=2)
def index():
    """
    Muestra los items de pedidos pendientes de planificación.
    """
    # Filtramos los items que están 'PENDIENTE' y no tienen una orden de producción asignada.
    items_result = pedido_model.find_all_items(filters={
        'estado': ('eq', 'PENDIENTE'),
        'orden_produccion_id': ('is', 'null')
    })
    
    items = []
    if items_result.get('success'):
        items = items_result.get('data', [])
    else:
        flash('Error al cargar los ítems para planificar.', 'error')
        
    return render_template('planificacion/index.html', items=items)

@planificacion_bp.route('/crear_orden', methods=['POST'])
@roles_required(allowed_roles=['GERENTE', 'SUPERVISOR'])
def crear_orden():
    """
    Crea órdenes de producción a partir de los items de pedido seleccionados.
    """
    selected_items_ids = request.form.getlist('item_ids')
    if not selected_items_ids:
        flash('No se seleccionó ningún ítem para planificar.', 'warning')
        return redirect(url_for('planificacion.index'))

    # Convertir IDs a enteros
    selected_items_ids = [int(id) for id in selected_items_ids]
    
    # Obtener los detalles completos de los items seleccionados
    items_result = pedido_model.find_all_items(filters={'id': ('in', selected_items_ids)})
    if not items_result.get('success'):
        flash('Error al obtener los detalles de los ítems seleccionados.', 'error')
        return redirect(url_for('planificacion.index'))
        
    all_items = items_result['data']
    
    # Agrupar items por producto_id
    all_items.sort(key=itemgetter('producto_id'))
    grouped_items = {k: list(v) for k, v in groupby(all_items, key=itemgetter('producto_id'))}
    
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        flash('Error de autenticación. Por favor, inicie sesión de nuevo.', 'error')
        return redirect(url_for('auth.login'))

    ordenes_creadas = 0
    errores = []

    # Crear una orden de producción por cada grupo de producto
    for producto_id, items_del_producto in grouped_items.items():
        item_ids_del_producto = [item['id'] for item in items_del_producto]
        
        resultado = orden_produccion_controller.crear_orden_desde_planificacion(
            producto_id=producto_id, 
            item_ids=item_ids_del_producto,
            usuario_id=usuario_id
        )
        
        if resultado.get('success'):
            ordenes_creadas += 1
        else:
            nombre_producto = items_del_producto[0].get('producto_nombre', f"ID {producto_id}")
            errores.append(f"Error al crear OP para '{nombre_producto}': {resultado.get('error')}")

    if ordenes_creadas > 0:
        flash(f'{ordenes_creadas} orden(es) de producción creadas exitosamente.', 'success')
    
    for error in errores:
        flash(error, 'error')

    return redirect(url_for('planificacion.index'))