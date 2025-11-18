from flask import Blueprint, render_template, request, jsonify
from app.utils.decorators import permission_required
from app.controllers.rentabilidad_controller import RentabilidadController

rentabilidad_bp = Blueprint('rentabilidad', __name__, url_prefix='/analisis')

@rentabilidad_bp.route('/rentabilidad', methods=['GET'])
@permission_required(accion='consultar_analisis_rentabilidad')
def pagina_rentabilidad():
    """
    Renderiza la página principal del análisis de rentabilidad.
    """
    return render_template('analisis/rentabilidad.html')

@rentabilidad_bp.route('/api/rentabilidad/datos', methods=['GET'])
@permission_required(accion='consultar_analisis_rentabilidad')
def api_datos_rentabilidad():
    """
    Endpoint de API para obtener los datos de la matriz de rentabilidad.
    Acepta 'fecha_inicio' y 'fecha_fin' como query parameters.
    """
    fecha_inicio = request.args.get('fecha_inicio', None)
    fecha_fin = request.args.get('fecha_fin', None)
    
    controller = RentabilidadController()
    response, status_code = controller.obtener_datos_matriz_rentabilidad(fecha_inicio, fecha_fin)
    return jsonify(response), status_code

@rentabilidad_bp.route('/api/rentabilidad/crecimiento', methods=['GET'])
@permission_required(accion='consultar_analisis_rentabilidad')
def api_crecimiento_ventas():
    """
    Endpoint de API para calcular el crecimiento de ventas.
    """
    periodo = request.args.get('periodo', 'mes')
    metrica = request.args.get('metrica', 'facturacion')
    controller = RentabilidadController()
    response, status_code = controller.calcular_crecimiento_ventas(periodo, metrica)
    return jsonify(response), status_code

@rentabilidad_bp.route('/api/rentabilidad/producto/<int:producto_id>', methods=['GET'])
@permission_required(accion='consultar_analisis_rentabilidad')
def api_detalles_producto(producto_id):
    """
    Endpoint de API para obtener los detalles de un producto específico.
    """
    controller = RentabilidadController()
    response, status_code = controller.obtener_detalles_producto(producto_id)
    return jsonify(response), status_code

@rentabilidad_bp.route('/api/rentabilidad/producto/<int:producto_id>/evolucion', methods=['GET'])
@permission_required(accion='consultar_analisis_rentabilidad')
def api_evolucion_producto(producto_id):
    """
    Endpoint de API para obtener la evolución histórica de un producto.
    """
    controller = RentabilidadController()
    response, status_code = controller.obtener_evolucion_producto(producto_id)
    return jsonify(response), status_code
