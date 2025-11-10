from flask import Blueprint, render_template, jsonify, request
from app.controllers.reportes_controller import ReportesController
from app.controllers.reporte_produccion_controller import ReporteProduccionController

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')
controller = ReportesController()
produccion_controller = ReporteProduccionController()

@reportes_bp.route('/')
def dashboard():
    return render_template('reportes/dashboard.html')

@reportes_bp.route('/api/ingresos_vs_egresos')
def api_ingresos_vs_egresos():
    periodo = request.args.get('periodo', 'semanal')
    data = controller.obtener_ingresos_vs_egresos(periodo)
    return jsonify(data)

@reportes_bp.route('/api/top_productos')
def api_top_productos():
    data = controller.obtener_top_productos()
    return jsonify(data)

@reportes_bp.route('/api/stock_critico')
def api_stock_critico():
    data = controller.obtener_stock_critico()
    return jsonify(data)

@reportes_bp.route('/produccion')
def produccion():
    return render_template('reportes/produccion.html')

# API Endpoints for Production Reports
@reportes_bp.route('/api/produccion/ordenes_por_estado')
def api_ordenes_por_estado():
    data = produccion_controller.obtener_ordenes_por_estado()
    return jsonify(data)

@reportes_bp.route('/api/produccion/composicion_produccion')
def api_composicion_produccion():
    data = produccion_controller.obtener_composicion_produccion()
    return jsonify(data)

@reportes_bp.route('/api/produccion/top_insumos')
def api_top_insumos():
    top_n = request.args.get('top_n', 5, type=int)
    data = produccion_controller.obtener_top_insumos(top_n)
    return jsonify(data)

@reportes_bp.route('/api/produccion/tiempo_ciclo_promedio')
def api_tiempo_ciclo_promedio():
    data = produccion_controller.obtener_tiempo_ciclo_promedio()
    return jsonify(data)

# @reportes_bp.route('/api/produccion/eficiencia_produccion')
# def api_eficiencia_produccion():
#     data = produccion_controller.obtener_eficiencia_produccion()
#     return jsonify(data)

@reportes_bp.route('/api/produccion/produccion_por_tiempo')
def api_produccion_por_tiempo():
    periodo = request.args.get('periodo', 'semanal')
    data = produccion_controller.obtener_produccion_por_tiempo(periodo)
    return jsonify(data)
