# app/routes/lote_producto_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_wtf import FlaskForm
from app.controllers.lote_producto_controller import LoteProductoController
from app.controllers.producto_controller import ProductoController # Para el formulario
from app.utils.decorators import permission_required
import logging
from datetime import date
from flask import jsonify


logger = logging.getLogger(__name__)

# lote_producto_bp = Blueprint("lote_producto", __name__)
lote_producto_bp = Blueprint("lote_producto", __name__, url_prefix="/lotes-productos")

@lote_producto_bp.route('/')
@permission_required(accion='almacen_consulta_stock')
def listar_lotes():
    controller = LoteProductoController()
    response, _ = controller.obtener_lotes_para_vista()
    lotes = response.get('data', [])

    grafico_resp_dict, _ = controller.obtener_datos_grafico_inventario()

    datos_grafico_productos = grafico_resp_dict.get('data', [])

    return render_template('lotes_productos/listar.html', lotes=lotes, datos_grafico_productos=datos_grafico_productos)

@lote_producto_bp.route('/<int:id_lote>/detalle')
@permission_required(accion='almacen_consulta_stock')
def detalle_lote(id_lote):
    controller = LoteProductoController()
    response, _ = controller.obtener_lote_por_id_para_vista(id_lote)
    if not response.get('success'):
        flash(response.get('error'), 'error')
        return redirect(url_for('lote_producto.listar_lotes'))

    return render_template('lotes_productos/detalle.html', lote=response.get('data'))


@lote_producto_bp.route('/nuevo', methods=['GET', 'POST'])
@jwt_required()
@permission_required(accion='crear_control_de_calidad_por_lote')
def nuevo_lote():
    controller = LoteProductoController()
    producto_controller = ProductoController()
    if request.method == 'POST':
        usuario_id = get_jwt_identity()
        response, status_code = controller.crear_lote_desde_formulario(request.form, usuario_id)
        if response.get('success'):
            flash(response.get('message'), 'success')
            return redirect(url_for('lote_producto.listar_lotes'))
        else:
            flash(response.get('error'), 'error')

    productos_resp_dict, _ = producto_controller.obtener_todos_los_productos()
    productos = productos_resp_dict.get('data', [])

    return render_template('lotes_productos/formulario.html',
                           productos=productos,
                           today=date.today().isoformat())

@lote_producto_bp.route("/lotes", methods=["GET"])
@permission_required(accion='consultar_reportes_historicos')
def obtener_lotes():
    """Obtiene todos los lotes."""
    try:
        controller = LoteProductoController()
        filtros = {}
        for key, value in request.args.items():
            if value and value != "":
                filtros[key] = value

        response, status = controller.obtener_lotes(filtros)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lotes: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/<int:lote_id>", methods=["GET"])
@permission_required(accion='consultar_reportes_historicos')
def obtener_lote_por_id(lote_id):
    """Obtiene un lote por su ID."""
    try:
        controller = LoteProductoController()
        response, status = controller.obtener_lote_por_id(lote_id)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lote_por_id: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/<int:lote_id>", methods=["PUT"])
@permission_required(accion='crear_control_de_calidad_por_lote')
def actualizar_lote(lote_id):
    """Actualiza un lote existente."""
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Content-Type debe ser application/json"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos JSON"}), 400

        controller = LoteProductoController()
        response, status = controller.actualizar_lote(lote_id, data)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en actualizar_lote: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/<int:lote_id>", methods=["DELETE"])
@permission_required(accion='registrar_desperdicios')
def eliminar_lote(lote_id):
    """Eliminación lógica de un lote."""
    try:
        controller = LoteProductoController()
        response, status = controller.eliminar_lote_logico(lote_id)
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en eliminar_lote: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

@lote_producto_bp.route("/lotes/disponibles", methods=["GET"])
@permission_required(accion='registrar_resultados_de_control')
def obtener_lotes_disponibles():
    """Obtiene lotes disponibles."""
    try:
        controller = LoteProductoController()
        response, status = controller.obtener_lotes({'estado': 'DISPONIBLE'})
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Error inesperado en obtener_lotes_disponibles: {str(e)}")
        return jsonify({"success": False, "error": "Error interno del servidor"}), 500

class UploadForm(FlaskForm):
    pass

@lote_producto_bp.route('/cargar-lotes-excel', methods=['GET', 'POST'])
@permission_required(accion='crear_control_de_calidad_por_lote')
def cargar_lotes_excel():
    """Muestra el formulario para cargar un archivo Excel con lotes de productos."""
    form = UploadForm()
    if form.validate_on_submit():
        if 'archivo' not in request.files:
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(request.url)

        archivo = request.files['archivo']

        if archivo.filename == '':
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(request.url)

        if archivo and (archivo.filename.endswith('.xlsx') or archivo.filename.endswith('.xls')):
            controller = LoteProductoController()
            response, status_code = controller.procesar_archivo_lotes(archivo)
            resultados = response.get('data') if response.get('success') else None
            error = response.get('error') if not response.get('success') else None

            return render_template('lotes_productos/cargar_lotes.html', form=form, resultados=resultados, error=error)
        else:
            flash('Formato de archivo no válido. Por favor, sube un archivo .xlsx o .xls.', 'error')
            return redirect(request.url)

    return render_template('lotes_productos/cargar_lotes.html', form=form, resultados=None, error=None)

@lote_producto_bp.route('/plantilla-lotes-excel', methods=['GET'])
@permission_required(accion='crear_control_de_calidad_por_lote')
def descargar_plantilla_lotes():
    """Descarga la plantilla de Excel para la carga masiva de lotes."""
    controller = LoteProductoController()
    output = controller.generar_plantilla_lotes()
    if output:
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='plantilla_carga_lotes.xlsx'
        )
    else:
        flash('Error al generar la plantilla de Excel.', 'error')
        return redirect(url_for('lote_producto.cargar_lotes_excel'))

@lote_producto_bp.route('/<int:id_lote>/cuarentena', methods=['POST'])
# @jwt_required()
# @permission_required(accion='gestionar_cuarentena_lotes')
def poner_en_cuarentena(id_lote):
    controller = LoteProductoController() # <-- AÑADIDO AQUÍ
    motivo = request.form.get('motivo_cuarentena')

    try:
        cantidad = float(request.form.get('cantidad_cuarentena'))
    except (TypeError, ValueError):
        flash('La cantidad debe ser un número válido.', 'danger')
        return redirect(url_for('lote_producto.listar_lotes'))

    response, status_code = controller.poner_lote_en_cuarentena(id_lote, motivo, cantidad)

    if response.get('success'):
        flash(response.get('message', 'Lote en cuarentena.'), 'success')
    else:
        flash(response.get('error', 'Error al procesar la solicitud.'), 'danger')

    return redirect(url_for('lote_producto.listar_lotes'))


@lote_producto_bp.route('/<int:id_lote>/liberar', methods=['POST'])
# @jwt_required()
# @permission_required(accion='gestionar_cuarentena_lotes')
def liberar_cuarentena(id_lote):
    controller = LoteProductoController() 
    try:
        cantidad = float(request.form.get('cantidad_a_liberar'))
    except (TypeError, ValueError):
        flash('La cantidad a liberar debe ser un número válido.', 'danger')
        return redirect(url_for('lote_producto.listar_lotes'))

    response, status_code = controller.liberar_lote_de_cuarentena(id_lote, cantidad)

    if response.get('success'):
        flash(response.get('message', 'Lote liberado.'), 'success')
    else:
        flash(response.get('error', 'Error al procesar la solicitud.'), 'danger')

    return redirect(url_for('lote_producto.listar_lotes'))


@lote_producto_bp.route('/<int:id_lote>/editar', methods=['GET', 'POST'])
# @jwt_required()
# @permission_required(accion='editar_lote_de_producto')
def editar_lote(id_lote):
    controller = LoteProductoController() # <-- AÑADIDO AQUÍ

    if request.method == 'POST':
        form_data = request.form
        response, status_code = controller.actualizar_lote_desde_formulario(id_lote, form_data)

        if response.get('success'):
            flash(response.get('message', 'Lote actualizado con éxito.'), 'success')
            return redirect(url_for('lote_producto.listar_lotes'))
        else:
            flash(response.get('error', 'Error al actualizar el lote.'), 'danger')

    response, status_code = controller.obtener_lote_por_id_para_vista(id_lote)

    if not response.get('success'):
        flash(response.get('error', 'Lote no encontrado.'), 'danger')
        return redirect(url_for('lote_producto.listar_lotes'))

    lote = response.get('data')

    return render_template('lotes_productos/editar_lote.html', lote=lote)

@lote_producto_bp.route('/<int:lote_id>/marcar-no-apto', methods=['POST'])
@jwt_required()
@permission_required(accion='crear_control_de_calidad_por_lote') # Or a more specific permission
def marcar_no_apto(lote_id):
    """
    Marca un lote de producto como 'NO APTO'.
    """
    controller = LoteProductoController()
    usuario_id = get_jwt_identity()
    
    response, status_code = controller.marcar_lote_como_no_apto(lote_id, usuario_id)

    if response.get('success'):
        flash(response.get('message', 'Lote marcado como No Apto.'), 'success')
    else:
        flash(response.get('error', 'Error al procesar la solicitud.'), 'danger')

    return redirect(url_for('lote_producto.detalle_lote', id_lote=lote_id))
