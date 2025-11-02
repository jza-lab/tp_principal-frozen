from flask import Blueprint, render_template, jsonify, request
from app.controllers.reportes_controller import ReportesController

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')
controller = ReportesController()

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
