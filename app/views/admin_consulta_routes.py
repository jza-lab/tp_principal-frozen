from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from app.controllers.consulta_controller import ConsultaController
from app.utils.decorators import permission_required

consulta_bp = Blueprint('consulta_admin', __name__, url_prefix='/admin/consultas')

@consulta_bp.route('/')
@permission_required(accion='admin_acceder_consultas')
def listar_consultas():
    consulta_controller = ConsultaController()
    consultas_response = consulta_controller.obtener_consultas()
    consultas = consultas_response.get('data', [])
    return render_template('consultas/listar.html', consultas=consultas)

@consulta_bp.route('/<int:consulta_id>/responder', methods=['GET', 'POST'])
@permission_required(accion='admin_acceder_consultas')
def responder_consulta(consulta_id):
    consulta_controller = ConsultaController()
    if request.method == 'POST':
        respuesta = request.form['respuesta']
        _, error = consulta_controller.responder_consulta(consulta_id, respuesta)
        if error:
            flash(error, 'danger')
        else:
            flash('Respuesta enviada con éxito.', 'success')
        return redirect(url_for('consulta_admin.listar_consultas'))

    consulta_response = consulta_controller.get_by_id(consulta_id)
    consulta = consulta_response.get('data')
    if not consulta:
        flash('Consulta no encontrada.', 'danger')
        return redirect(url_for('consulta_admin.listar_consultas'))
    return render_template('consultas/responder.html', consulta=consulta)
