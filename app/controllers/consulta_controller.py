# app/controllers/consulta_controller.py
from .base_controller import BaseController
from app.models.consulta import ConsultaModel
from app.models.cliente import ClienteModel
from app.services.email_service import send_email
from flask import current_app
from datetime import datetime

class ConsultaController(BaseController):
    def __init__(self):
        super().__init__()
        self.model = ConsultaModel()
        self.cliente_model = ClienteModel()

    def crear_consulta(self, data):
        cliente_response = self.cliente_model.find_all(filters={'email': data['email']})
        if cliente_response.get('success') and cliente_response.get('data'):
            cliente_data = cliente_response['data'][0]
            if 'cliente_id' not in data:
                 return None, "El email ya está registrado. Por favor, inicia sesión para enviar una consulta."
            data['cliente_id'] = cliente_data['id']
        result = self.model.create(data)
        if not result.get('success'):
            return None, result.get('error', 'Ocurrió un error desconocido al crear la consulta.')
        return result.get('data'), None

    def obtener_consultas(self, filtros=None):
        return self.model.find_all(filters=filtros)
    
    def get_by_id(self, consulta_id):
        return self.model.find_by_id(consulta_id)

    def responder_consulta(self, consulta_id, respuesta):
        
        # --- PASO 1: OBTENER DATOS ANTES DE ACTUALIZAR ---
        consulta_original_response = self.get_by_id(consulta_id)
        if not consulta_original_response.get('success') or not consulta_original_response.get('data'):
            return None, "Error: No se pudo encontrar la consulta original para responder."

        consulta_data = consulta_original_response['data']
        
        # Guardamos los datos que necesitamos para el email EN VARIABLES
        to_email = consulta_data.get('email')
        nombre_cliente = consulta_data.get('nombre', 'Cliente')
        consulta_original = consulta_data.get('mensaje')

        
        # --- PASO 2: ACTUALIZAR LA CONSULTA EN LA BD ---
        
        # 1. Empezamos con TODOS los datos originales que ya teníamos
        updated_data = consulta_data 
        
        # 2. Modificamos SÓLO los campos que nos interesan
        updated_data['respuesta'] = respuesta
        updated_data['estado'] = 'respondida'
        
        # 3. Ahora, cuando llamemos a update, 'updated_data' contiene
        result = self.model.update(consulta_id, updated_data)
        if not result.get('success'):
            return None, result.get('error', 'Error al actualizar la consulta en la base de datos.')
        

        # --- PASO 3: PREPARAR Y ENVIAR EL EMAIL ---
        
        subject = "Respuesta a tu consulta en FrozenProd"
        respuesta_html = respuesta.replace('\n', '<br>')
        
        body_html = f"""
        <html>
        <head>
            <style>
                body {{
                    margin: 0; padding: 0; font-family: 'Poppins', sans-serif;
                    line-height: 1.6; background-color: #EBF5FB;
                }}
                .container {{
                    width: 90%; max-width: 600px; margin: 20px auto;
                    border: 1px solid #A2B9D8; border-radius: 12px;
                    overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.07);
                    background-color: #FFFFFF; color: #333333;
                }}
                .header {{
                    background: #347E85; padding: 30px 20px;
                    text-align: center; border-bottom: 5px solid #4BA0A0;
                }}
                .header img {{ max-width: 100px; margin-bottom: 15px; }}
                .header h1 {{ color: #FFFFFF; margin: 0; font-size: 28px; }}
                .content {{ padding: 35px; }}
                .content p {{ margin-bottom: 20px; font-size: 16px; }}
                .response-box {{
                    background-color: #EBF5FB; border-left: 5px solid #347E85;
                    padding: 20px; margin-top: 20px; margin-bottom: 30px; border-radius: 5px;
                }}
                .original-query {{
                    background-color: #FFFFFF; border: 1px dashed #A2B9D8;
                    padding: 20px; margin-top: 25px; border-radius: 8px;
                    font-style: italic; color: #555;
                }}
                .original-query strong {{ color: #333333; font-style: normal; }}
                .footer {{
                    background-color: #333333; color: #EBF5FB;
                    padding: 25px; text-align: center; font-size: 12px;
                }}
                .footer p {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>FrozenProd</h1>
                </div>
                <div class="content">
                    <p>Hola, <strong>{nombre_cliente}</strong>:</p>
                    <p>Hemos respondido tu consulta. Aquí está nuestra respuesta:</p>

                    <div class="response-box">
                        <p>{respuesta_html}</p>
                    </div>

                    <div class="original-query">
                        <p><strong>Tu consulta original:</strong></p>
                        <p>"{consulta_original}"</p>
                    </div>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.now().year} FrozenProd. Todos los derechos reservados.</p>
                    <p>Este es un email automático, por favor no respondas a esta dirección.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        with current_app.app_context():
            email_sent, email_error = send_email(to_email, subject, body_html)
        
        if not email_sent:
            print(f"Advertencia: La consulta {consulta_id} fue actualizada pero el email no pudo ser enviado: {email_error}")

        return result.get('data'), None

    def obtener_consultas_por_cliente(self, cliente_id):
        return self.model.find_all(
            filters={'cliente_id': cliente_id},
            select_query='*'
        )

    def obtener_conteo_consultas_pendientes(self):
        response = self.model.find_all(
            filters={'estado': 'pendiente'}
        )
        if response.get('success') and response.get('data'):
            return len(response['data'])
        return 0