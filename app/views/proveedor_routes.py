from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_jwt_extended import jwt_required
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.proveedor_controller import ProveedorController

proveedor_bp = Blueprint('proveedor', __name__, url_prefix='/proveedores')

@proveedor_bp.route('/<int:id>/ordenes_compra', methods=['GET'])
@jwt_required()
def historial_ordenes_compra(id):
    """
    Muestra el historial de órdenes de compra para un proveedor específico,
    incluyendo detalles de calidad.
    """
    proveedor_controller = ProveedorController()
    orden_compra_controller = OrdenCompraController()

    # Obtener datos del proveedor
    proveedor_result, _ = proveedor_controller.obtener_proveedor(id)
    if not proveedor_result.get('success'):
        flash('Proveedor no encontrado.', 'error')
        return redirect(url_for('main.index')) # Redirigir a una página principal
    
    proveedor = proveedor_result.get('data')

    # Obtener órdenes de compra del proveedor
    oc_result, _ = orden_compra_controller.get_all_ordenes(filtros={'proveedor_id': id})
    if not oc_result.get('success'):
        flash('Error al obtener las órdenes de compra.', 'error')
        ordenes_compra = []
    else:
        ordenes_compra = oc_result.get('data')

    return render_template('proveedores/historial_oc.html', 
                           proveedor=proveedor, 
                           ordenes_compra=ordenes_compra)
