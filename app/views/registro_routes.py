from flask import Blueprint, render_template
from flask_jwt_extended import jwt_required
from app.utils.decorators import permission_required
from app.controllers.registro_controller import RegistroController

registros_bp = Blueprint('registros', __name__, url_prefix='/registros')

@registros_bp.route('/')
@jwt_required()
@permission_required(accion='ver_registros')
def listar_registros():
    registro_controller = RegistroController()
    categorias = {
        "Insumos": "Insumos",
        "Productos": "Productos",
        "Ordenes de compra": "Ordenes de compra",
        "Ordenes de venta": "Ordenes de venta",
        "Ordenes de produccion": "Ordenes de produccion",
        "Empleados": "Empleados",
        "Autorizaciones": "Autorizaciones",
        "Clientes": "Clientes",
        "Proveedores": "Proveedores",
        "Reclamos": "Reclamos",
        "Accesos": "Accesos",
        "Alertas Insumos": "Alertas Insumos",
        "Alertas Lotes": "Alertas Lotes",
        "Alertas Productos": "Alertas Productos"
    }
    
    registros_por_categoria = {}
    for nombre_amigable, categoria_db in categorias.items():
        registros = registro_controller.obtener_registros_por_categoria(categoria_db)
        registros_por_categoria[nombre_amigable] = registros

    return render_template('registros/listar.html', registros_por_categoria=registros_por_categoria)
