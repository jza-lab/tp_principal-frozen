from .base_controller import BaseController
from app.models.consulta import ConsultaModel
from app.models.cliente import ClienteModel
from app.services.email_service import send_email
from flask import current_app

class ConsultaController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = ConsultaModel()
        self.cliente_model = ClienteModel()

    def crear_consulta(self, data):
        # Check if email belongs to a registered client
        cliente_response = self.cliente_model.find_all(filters={'email': data['email']})
        
        # CORRECT ACCESS METHOD
        if cliente_response.get('success') and cliente_response.get('data'):
            cliente_data = cliente_response['data'][0]
            # If the user is not logged in, but the email is registered
            if 'cliente_id' not in data:
                 return None, "El email ya está registrado. Por favor, inicia sesión para enviar una consulta."
            data['cliente_id'] = cliente_data['id']

        result = self.model.create(data)
        
        # CORRECT ERROR HANDLING
        if not result.get('success'):
            return None, result.get('error', 'Ocurrió un error desconocido al crear la consulta.')
        
        return result.get('data'), None

    def obtener_consultas(self, filtros=None):
        return self.model.find_all(filters=filtros)
    
    def get_by_id(self, consulta_id):
        return self.model.find_by_id(consulta_id)

    def responder_consulta(self, consulta_id, respuesta):
        updated_data = {
            'respuesta': respuesta,
            'estado': 'respondida'
        }
        result = self.model.update(consulta_id, updated_data)
        if not result.get('success'):
            return None, result.get('error')
        
        consulta_actualizada = result['data']
        to_email = consulta_actualizada['email']
        subject = "Respuesta a tu consulta en Sistema Frozen"
        
        with current_app.app_context():
            email_sent, email_error = send_email(to_email, subject, respuesta)
        
        if not email_sent:
            print(f"Advertencia: La consulta {consulta_id} fue actualizada pero el email no pudo ser enviado: {email_error}")

        return result.get('data'), None

    def obtener_consultas_por_cliente(self, cliente_id):
        return self.model.find_all(filters={'cliente_id': cliente_id})

    def obtener_conteo_consultas_pendientes(self):
        response = self.model.find_all(
            filters={'estado': 'pendiente'}
        )
        if response.get('success') and response.get('data'):
            return len(response['data'])
        return 0