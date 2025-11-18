from flask import Blueprint, jsonify, request, render_template
from app.controllers.trazabilidad_controller import TrazabilidadController

api_trazabilidad_bp = Blueprint('api_trazabilidad', __name__, url_prefix='/api/trazabilidad')

@api_trazabilidad_bp.route('/template', methods=['GET'])
def get_pdf_template():
    """
    Devuelve el contenido HTML de la plantilla de exportación de PDF.
    """
    return render_template('trazabilidad/_documento_trazabilidad.html')

@api_trazabilidad_bp.route('/company_info', methods=['GET'])
def get_company_info():
    """
    Devuelve la información de la empresa para ser usada en los PDFs.
    """
    company_data = {
        "nombre": "FrozenProd S.A.",
        "cuit": "30-71000000-8",
        "domicilio": "Juan María Gutiérrez 1150, Los Polvorines, Provincia de Buenos Aires"
    }
    return jsonify(company_data)

@api_trazabilidad_bp.route('/<string:tipo_entidad>/<string:id>', methods=['GET'])
def get_trazabilidad_unificada(tipo_entidad, id):
    """
    Endpoint unificado para obtener los datos de trazabilidad para cualquier entidad.
    Acepta un parámetro 'nivel' en la URL (?nivel=simple o ?nivel=completo).
    Por defecto, el nivel es 'simple'.
    """
    nivel = request.args.get('nivel', 'simple')
    controller = TrazabilidadController()
    response, status_code = controller.obtener_trazabilidad(tipo_entidad, id, nivel)
    return jsonify(response), status_code
