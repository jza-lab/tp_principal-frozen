from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    jsonify,
    session,
    url_for,
    flash,
)
from app.controllers.insumo_controller import InsumoController
from app.controllers.producto_controller import ProductoController
from app.controllers.inventario_controller import InventarioController
from app.controllers.orden_compra_controller import OrdenCompraController
from app.controllers.usuario_controller import UsuarioController
from app.controllers.receta_controller import RecetaController
from app.utils.decorators import permission_required, permission_any_of
from app.utils.validators import validate_uuid
from marshmallow import ValidationError
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# The url_prefix will be handled in app/__init__.py
productos_bp = Blueprint("productos", __name__)

insumo_controller = InsumoController()
producto_controller = ProductoController()
receta_controller = RecetaController()
ordenes_compra_controller = OrdenCompraController()
inventario_controller = InventarioController()
usuario_controller = UsuarioController()


@productos_bp.route("/catalogo/nuevo", methods=["GET", "POST"])
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario')
def crear_producto():
    try:
        if request.method == "POST":
            datos_json = request.get_json()
            if not datos_json:
                return jsonify(
                    {"success": False, "error": "No se recibieron datos JSON válidos"}
                ), 400
            # Correctly unpack the response from the controller
            response, status = producto_controller.crear_producto(datos_json)
            return jsonify(response), status

        # For GET request
        producto = None
        insumos_resp, _ = insumo_controller.obtener_insumos()
        insumos = insumos_resp.get("data", [])
        roles = usuario_controller.obtener_todos_los_roles()
        return render_template("productos/formulario.html", producto=producto, receta_items=[], is_edit=False, insumos=insumos, roles=roles, receta=None)
    except Exception as e:
        logger.error(f"Error inesperado en crear_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@productos_bp.route("/catalogo", methods=["GET"])
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario', 'produccion_consulta', 'almacen_consulta_stock')
def obtener_productos():
    try:
        filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}

        response, status = producto_controller.obtener_todos_los_productos(filtros)

        if status == 200:
            productos = response.get("data", [])
        else:
            flash(response.get("error", "Error al cargar los productos."), "error")
            productos = []

        categorias_response, _ = producto_controller.obtener_categorias_distintas()
        categorias = categorias_response.get("data", [])

        return render_template(
            "productos/listar.html",
            productos=productos,
            categorias=categorias
        )
    except Exception as e:
        logger.error(f"Error inesperado en obtener_productos: {str(e)}")
        flash("Ocurrió un error inesperado al cargar la página de productos.", "error")
        return redirect(url_for('productos.obtener_productos'))


@productos_bp.route("/catalogo/<int:id_producto>", methods=["GET"])
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario', 'produccion_consulta', 'almacen_consulta_stock')
def obtener_producto_por_id(id_producto):
    try:
        producto_resp = producto_controller.obtener_producto_por_id(id_producto)
        if not producto_resp.get('success'):
            flash(producto_resp.get('error', 'Producto no encontrado.'), 'error')
            return redirect(url_for('productos.obtener_productos'))
        
        producto = producto_resp['data']

        receta_completa = None
        receta_items = []
        receta_response = receta_controller.model.db.table('recetas').select('id').eq('producto_id', id_producto).execute()
        
        if receta_response.data:
            receta_id = receta_response.data[0]['id']
            receta_resp, _ = receta_controller.obtener_receta_con_ingredientes(receta_id)
            if receta_resp.get('success'):
                receta_completa = receta_resp['data']
                receta_items = receta_completa.get("ingredientes", [])
                
                # Enriquecer los nombres de los roles en las operaciones
                roles_map = {rol['id']: rol['nombre'] for rol in usuario_controller.obtener_todos_los_roles()}
                if 'operaciones' in receta_completa:
                    for op in receta_completa['operaciones']:
                        op['roles_nombres'] = [roles_map.get(rol_id, 'N/A') for rol_id in op.get('roles_asignados', [])]
        
        response_insumos, status_insumo = insumo_controller.obtener_insumos()
        insumos = response_insumos.get("data", [])
        insumos_dict = {str(insumo['id_insumo']): insumo for insumo in insumos}
        for item in receta_items:
            insumo = insumos_dict.get(str(item['id_insumo']))
            if insumo:
                item['nombre_insumo'] = insumo.get('nombre', 'Insumo no encontrado')
                item['precio_unitario'] = insumo.get('precio_unitario', 0)
            else:
                item['nombre_insumo'] = 'Insumo no encontrado'
                item['precio_unitario'] = 0

        # Pasar el producto y la receta (que contiene las operaciones) por separado
        return render_template("productos/perfil_producto.html", producto=producto, receta=receta_completa, receta_items=receta_items)

    except Exception as e:
        logger.error(f"Error inesperado en obtener_producto_por_id: {e}", exc_info=True)
        flash("Ocurrió un error al cargar el detalle del producto.", "error")
        return redirect(url_for("productos.obtener_productos"))

@productos_bp.route(
    "/catalogo/actualizar/<int:id_producto>", methods=["GET", "POST", "PUT"]
)
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario')
def actualizar_producto(id_producto):
    try:
        if request.method == "PUT" or request.method == "POST":
            datos_payload = None
            if request.is_json:
                datos_payload = request.get_json()
            else:
                form_data = request.form
                datos_payload = {
                    "nombre": form_data.get('nombre'),
                    "categoria": form_data.get('categoria'),
                    "unidad_medida": form_data.get('unidad_medida'),
                    "descripcion": form_data.get('descripcion'),
                    "porcentaje_ganancia": form_data.get('porcentaje_ganancia'),
                    "iva": 'iva' in form_data,
                    "vida_util_dias": form_data.get('vida_util_dias'),
                    "receta_items": [],
                    "operaciones": []
                }
                # Procesar ingredientes
                insumo_ids = form_data.getlist('insumo_id[]')
                cantidades = form_data.getlist('cantidad[]')
                for i in range(len(insumo_ids)):
                    datos_payload['receta_items'].append({
                        'id_insumo': insumo_ids[i],
                        'cantidad': cantidades[i]
                    })
                
                # Procesar operaciones
                nombres_op = form_data.getlist('operacion_nombre[]')
                preps_op = form_data.getlist('operacion_prep[]')
                ejecs_op = form_data.getlist('operacion_ejec[]')
                secuencias_op = form_data.getlist('operacion_secuencia[]')

                for i in range(len(nombres_op)):
                    secuencia = secuencias_op[i]
                    roles = form_data.getlist(f'operacion_roles_{secuencia}[]')
                    datos_payload['operaciones'].append({
                        'nombre_operacion': nombres_op[i],
                        'tiempo_preparacion': preps_op[i],
                        'tiempo_ejecucion_unitario': ejecs_op[i],
                        'secuencia': secuencia,
                        'roles': roles
                    })

            if not datos_payload:
                return jsonify({"success": False, "error": "No se recibieron datos válidos"}), 400
            
            response, status = producto_controller.actualizar_producto(id_producto, datos_payload)
            
            # Si el request no fue JSON (envío tradicional), redirigir en lugar de devolver JSON
            if not request.is_json:
                if status == 200:
                    flash('Producto actualizado correctamente.', 'success')
                    return redirect(url_for('productos.obtener_productos'))
                else:
                    flash(response.get('error', 'Ocurrió un error al actualizar.'), 'error')
                    return redirect(url_for('productos.actualizar_producto', id_producto=id_producto))

            return jsonify(response), status

        response_producto = producto_controller.obtener_producto_por_id(id_producto)
        if not response_producto.get('success'):
            flash(response_producto.get('error', 'Producto no encontrado.'), 'error')
            return redirect(url_for('productos.obtener_productos'))

        producto = response_producto.get('data')
        if not producto:
            flash("Producto no encontrado.", "error")
            return redirect(url_for('productos.obtener_productos'))

        response_insumos, status_insumo = insumo_controller.obtener_insumos()
        insumos = response_insumos.get("data", [])
        roles = usuario_controller.obtener_todos_los_roles()

        receta_items = []
        receta_completa = None
        receta_response = receta_controller.model.db.table('recetas').select('id').eq('producto_id', id_producto).execute()
        if receta_response.data:
            receta_id = receta_response.data[0]['id']
            receta_resp, _ = receta_controller.obtener_receta_con_ingredientes(receta_id)
            if receta_resp.get('success'):
                receta_completa = receta_resp['data']
                receta_items = receta_completa.get("ingredientes", [])

        insumos_dict = {str(insumo['id']): insumo for insumo in insumos}

        for item in receta_items:
            insumo = insumos_dict.get(str(item['id_insumo']))
            if insumo:
                item['precio_unitario'] = insumo.get('precio_unitario', 0)
                item['unidad_medida'] = insumo.get('unidad_medida', '')
            else:
                item['precio_unitario'] = 0
                item['unidad_medida'] = ''
        
        return render_template("productos/formulario.html", producto=producto, insumos=insumos, is_edit=True, receta_items=receta_items, roles=roles, receta=receta_completa)
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@productos_bp.route(
    "/catalogo/actualizar-precio/<int:id_producto>", methods=["GET", "PUT", "POST"]
)
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario')
def actualizar_precio(id_producto):
    try:
        # La lógica de recálculo ya está en el controlador, solo necesitamos llamarla.
        resultado = producto_controller._recalcular_costos_producto(id_producto)
        if resultado.get('success'):
            # Opcional: obtener el producto actualizado para devolver datos frescos
            producto_actualizado_res = producto_controller.obtener_producto_por_id(id_producto)
            return jsonify({
                "success": True, 
                "message": "Costos y precio del producto actualizados.",
                "data": producto_actualizado_res.get('data')
            }), 200
        else:
            return jsonify({"success": False, "error": resultado.get('error', 'Error al recalcular costos.')}), 500
    except Exception as e:
        logger.error(f"Error inesperado en actualizar_precio: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@productos_bp.route("/catalogo/eliminar/<string:id_producto>", methods=["DELETE"])
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario')
def eliminar_producto(id_producto):
    try:
        response, status = producto_controller.eliminar_producto_logico(id_producto)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en eliminar_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500


@productos_bp.route("/catalogo/habilitar/<string:id_producto>", methods=["POST"])
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario')
def habilitar_producto(id_producto):
    try:
        response, status = producto_controller.habilitar_producto(id_producto)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en habilitar_producto: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@productos_bp.route("/api/catalogo/buscar", methods=["GET"])
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario', 'produccion_consulta', 'almacen_consulta_stock')
def buscar_productos_api():
    try:
        filtros = {k: v for k, v in request.args.items() if v is not None and v != ""}
        response, status = producto_controller.obtener_todos_los_productos(filtros)
        if status == 200:
            return jsonify(response.get("data", [])), 200
        else:
            return jsonify({"error": response.get("error", "Error al buscar productos.")}), status
    except Exception as e:
        logger.error(f"Error inesperado en buscar_productos_api: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500

@productos_bp.route("/api/catalogo/recalcular-costos", methods=["POST"])
@permission_any_of('gestionar_orden_de_produccion', 'gestionar_inventario')
def recalcular_costos_api():
    try:
        data = request.get_json()
        operaciones_data = data.get('operaciones', [])
        
        response, status = producto_controller.recalcular_costos_dinamicos(operaciones_data)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error inesperado en recalcular_costos_api: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500
