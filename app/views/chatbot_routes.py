from flask import Blueprint, jsonify, request, render_template
from app.controllers.chatbot_controller import ChatbotController
from app.utils.decorators import jwt_required, permission_required, roles_required

chatbot_bp = Blueprint('chatbot', __name__)
chatbot_controller = ChatbotController()

# --- Rutas Públicas ---
@chatbot_bp.route('/api/chatbot/qas', methods=['GET'], endpoint='get_active_qas')
def get_active_qas():
    """Endpoint público para que el chatbot obtenga las Q&As activas de nivel superior."""
    return chatbot_controller.get_all_active_qas()

@chatbot_bp.route('/api/chatbot/qas/<int:parent_id>/children', methods=['GET'], endpoint='get_children_qas')
def get_children_qas(parent_id):
    """Endpoint público para obtener las Q&As hijas."""
    return chatbot_controller.get_children_qas(parent_id)

# --- Rutas de Administración ---
@chatbot_bp.route('/admin/chatbot/qas', methods=['GET'], endpoint='get_all_qas_admin')
@jwt_required()
@permission_required('admin_gestion_sistema')
def get_all_qas():
    """Endpoint para que el admin vea todas las Q&As."""
    return chatbot_controller.get_all_qas_for_admin()

@chatbot_bp.route('/admin/chatbot/qas', methods=['POST'], endpoint='create_qa_admin')
@jwt_required()
@permission_required('admin_gestion_sistema')
def create_qa():
    """Endpoint para que el admin cree una nueva Q&A."""
    data = request.form
    return chatbot_controller.create_qa(data)

@chatbot_bp.route('/admin/chatbot/qas/<int:qa_id>', methods=['PUT'], endpoint='update_qa_admin')
@jwt_required()
@permission_required('admin_gestion_sistema')
def update_qa(qa_id):
    """Endpoint para que el admin actualice una Q&A."""
    data = request.form
    return chatbot_controller.update_qa(qa_id, data)

@chatbot_bp.route('/admin/chatbot/qas/<int:qa_id>/toggle', methods=['PATCH'], endpoint='toggle_qa_admin')
@jwt_required()
@permission_required('admin_gestion_sistema')
def toggle_qa(qa_id):
    """Endpoint para que el admin active/desactive una Q&A."""
    data = request.form
    return chatbot_controller.toggle_qa_active(qa_id, data)

@chatbot_bp.route('/admin/chatbot/qas/<int:qa_id>', methods=['DELETE'], endpoint='delete_qa_admin')
@jwt_required()
@permission_required('admin_gestion_sistema')
def delete_qa(qa_id):
    """Endpoint para que el admin elimine (lógicamente) una Q&A."""
    return chatbot_controller.delete_qa(qa_id)

@chatbot_bp.route('/admin/chatbot', methods=['GET'], endpoint='gestion_chatbot_page')
@jwt_required()
@permission_required('admin_gestion_sistema')
def gestion_chatbot_page():
    """Renderiza la página de administración del chatbot."""
    return render_template('admin/gestion_chatbot.html')