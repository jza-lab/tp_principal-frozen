from flask import Blueprint, render_template, request
from flask_jwt_extended import jwt_required
from app.utils.decorators import permission_required
from app.controllers.registro_controller import RegistroController
from datetime import datetime
import pytz

registros_bp = Blueprint('registros', __name__, url_prefix='/registros')

@registros_bp.route('/')
#@jwt_required()
#@permission_required(accion='ver_registros')
def listar_registros():
    # Obtener los parámetros de la URL para saber qué pestaña activar
    active_main_tab = request.args.get('tab', 'tab-Insumos')
    active_sub_tab = request.args.get('subtab', None)

    registro_controller = RegistroController()
    
    categorias = {
        "Insumos": None, "Productos": None, "Ordenes de compra": None,
        "Ordenes de venta": None, "Ordenes de produccion": None,
        "Gestion de Empleados": {"Empleados": "Empleados", "Autorizaciones": "Autorizaciones"},
        "Clientes": None, "Proveedores": None, "Reclamos": None, "Accesos": None,
        "Alertas": {
            "Insumos": "Alertas Insumos", "Lotes": "Alertas Lotes", "Productos": "Alertas Productos"
        }
    }

    todos_los_registros = registro_controller.obtener_todos_los_registros()
    
    mapa_db_a_amigable = {}
    for nombre_amigable, subcategorias in categorias.items():
        if subcategorias:
            for sub_nombre, sub_db in subcategorias.items():
                mapa_db_a_amigable[sub_db] = (nombre_amigable, sub_nombre)
        else:
            mapa_db_a_amigable[nombre_amigable] = (nombre_amigable, None)

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
    
    art_timezone = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_actualizacion = datetime.now(art_timezone).strftime('%d/%m/%Y %H:%M:%S')
    
    return render_template('registros/listar.html', 
                           registros_agrupados=registros_agrupados, 
                           categorias=categorias,
                           fecha_actualizacion=fecha_actualizacion,
                           active_main_tab=active_main_tab,
                           active_sub_tab=active_sub_tab)
