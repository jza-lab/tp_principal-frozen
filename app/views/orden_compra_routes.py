from flask import Blueprint
from app.controllers.orden_compra_controller import OrdenCompraController

orden_compra_bp = Blueprint('orden_compra', __name__)
controller = OrdenCompraController()

@orden_compra_bp.route('/create/ordenes-compra', methods=['POST'])
def create_orden():
    return controller.create_orden()

@orden_compra_bp.route('/get/all/ordenes-compra', methods=['GET'])
def get_all_ordenes():
    return controller.get_all_ordenes()

@orden_compra_bp.route('/get/id/ordenes-compra/<int:orden_id>', methods=['GET'])
def get_orden(orden_id):
    return controller.get_orden(orden_id)

@orden_compra_bp.route('/modify/ordenes-compra/<int:orden_id>', methods=['PUT'])
def update_orden(orden_id):
    return controller.update_orden(orden_id)

@orden_compra_bp.route('/get/codigo-oc/ordenes-compra/codigo/<string:codigo_oc>', methods=['GET'])
def get_orden_by_codigo(codigo_oc):
    return controller.get_orden_by_codigo(codigo_oc)

@orden_compra_bp.route('/ordenes-compra/<int:orden_id>/cancelar', methods=['POST'])
def cancelar_orden(orden_id):
    return controller.cancelar_orden(orden_id)