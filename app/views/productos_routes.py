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
from app.controllers.costo_fijo_controller import CostoFijoController
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
costo_fijo_controller = CostoFijoController()


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
        
        costos_fijos_res, _ = costo_fijo_controller.get_all_costos_fijos({'activo': True})
        costos_fijos = costos_fijos_res.get('data', [])

        return render_template("productos/formulario.html", producto=producto, receta_items=[], is_edit=False, insumos=insumos, roles=roles, costos_fijos=costos_fijos, receta=None)
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
        response_producto = producto_controller.obtener_producto_por_id(id_producto)
        
        if not response_producto.get('success'):
             flash(response_producto.get('error', 'Producto no encontrado'), 'error')
             return redirect(url_for("productos.obtener_productos"))

        producto = response_producto.get('data')

        response_insumos, status_insumo = insumo_controller.obtener_insumos()
        insumos = response_insumos.get("data", [])

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
                
                # Obtener mapa de Costos Fijos para mostrar nombres
                # Updated: use 'nombre_costo' based on findings
                costos_fijos_res, _ = costo_fijo_controller.get_all_costos_fijos({'activo': True})
                costos_fijos_map = {c['id']: c.get('nombre_costo', c.get('nombre', 'Desconocido')) for c in costos_fijos_res.get('data', [])}

                if 'operaciones' in receta_completa:
                    for op in receta_completa['operaciones']:
                        # Formatear Roles: "Nombre (50%)"
                        op['roles_display'] = []
                        for rol_info in op.get('roles_detalle', []):
                            nombre = roles_map.get(rol_info['rol_id'], 'N/A')
                            pct = rol_info.get('porcentaje_participacion', 100)
                            op['roles_display'].append(f"{nombre} ({pct}%)")
                        
                        # Formatear Costos Fijos
                        op['costos_fijos_nombres'] = [costos_fijos_map.get(cf_id, 'Desconocido') for cf_id in op.get('costos_fijos_ids', [])]

        
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
            # Nota: El frontend ahora envía JSON complejo, así que request.form se usará menos.
            # Mantengo el soporte JSON principalmente.
            datos_payload = None
            if request.is_json:
                datos_payload = request.get_json()
            else:
                # Fallback para form-data tradicional (aunque con la nueva estructura de roles anidados es difícil que funcione bien sin JS)
                # Se recomienda encarecidamente usar el envío JSON del frontend actualizado.
                return jsonify({"success": False, "error": "Este formulario requiere envío JSON."}), 400

            if not datos_payload:
                return jsonify({"success": False, "error": "No se recibieron datos válidos"}), 400
            
            response, status = producto_controller.actualizar_producto(id_producto, datos_payload)
            
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
        
        costos_fijos_res, _ = costo_fijo_controller.get_all_costos_fijos({'activo': True})
        costos_fijos = costos_fijos_res.get('data', [])

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
        
        return render_template("productos/formulario.html", producto=producto, insumos=insumos, is_edit=True, receta_items=receta_items, roles=roles, costos_fijos=costos_fijos, receta=receta_completa)
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
