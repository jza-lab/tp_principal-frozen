from flask import Blueprint, render_template
from flask_jwt_extended import jwt_required
from app.utils.decorators import permission_required
from app.controllers.registro_controller import RegistroController
from datetime import datetime

registros_bp = Blueprint('registros', __name__, url_prefix='/registros')

@registros_bp.route('/')
#@jwt_required()
#@permission_required(accion='ver_registros')
def listar_registros():
    registro_controller = RegistroController()
    
    # Nueva estructura de categorías anidadas
    categorias = {
        "Insumos": None,
        "Productos": None,
        "Ordenes de compra": None,
        "Ordenes de venta": None,
        "Ordenes de produccion": None,
        "Gestion de Empleados": {
            "Empleados": "Empleados",
            "Autorizaciones": "Autorizaciones"
        },
        "Clientes": None,
        "Proveedores": None,
        "Reclamos": None,
        "Accesos": None,
        "Alertas": {
            "Insumos": "Alertas Insumos",
            "Lotes": "Alertas Lotes",
            "Productos": "Alertas Productos"
        }
    }

    todos_los_registros = registro_controller.obtener_todos_los_registros()
    
    # Aplanar el mapa de categorías para buscar registros
    mapa_db_a_amigable = {}
    for nombre_amigable, subcategorias in categorias.items():
        if subcategorias:
            for sub_nombre, sub_db in subcategorias.items():
                mapa_db_a_amigable[sub_db] = (nombre_amigable, sub_nombre)
        else:
            # Asumimos que el nombre amigable es el mismo que en la BD si no hay subcategorías
            mapa_db_a_amigable[nombre_amigable] = (nombre_amigable, None)

    # Inicializar la estructura de datos para la plantilla
    registros_agrupados = {nombre: ({} if subcategorias else []) for nombre, subcategorias in categorias.items()}

    for registro in todos_los_registros:
        categoria_db = registro.get('categoria')
        if categoria_db in mapa_db_a_amigable:
            grupo_principal, subgrupo = mapa_db_a_amigable[categoria_db]
            
            if subgrupo:
                if subgrupo not in registros_agrupados[grupo_principal]:
                    registros_agrupados[grupo_principal][subgrupo] = []
                registros_agrupados[grupo_principal][subgrupo].append(registro)
            else:
                registros_agrupados[grupo_principal].append(registro)
    
    fecha_actualizacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('registros/listar.html', registros_agrupados=registros_agrupados, categorias=categorias, fecha_actualizacion=fecha_actualizacion)
