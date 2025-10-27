from app.models.reclamo import ReclamoModel
from app.schemas.reclamo_schema import ReclamoSchema
from marshmallow import ValidationError
from flask_wtf import FlaskForm

class ReclamoController:
    """
    Controlador para gestionar la lógica de negocio de los reclamos.
    """
    def __init__(self):
        self.model = ReclamoModel()
        self.schema = ReclamoSchema()



    def crear_reclamo(self, datos_json, cliente_id):
        """
        Valida los datos de un nuevo reclamo y lo crea en la base de datos.

        Args:
            datos_json (dict): Los datos del reclamo recibidos en la solicitud.
            cliente_id (int): El ID del cliente que realiza el reclamo, obtenido de la sesión.
        
        Returns:
            tuple: Una tupla con un diccionario de respuesta y un código de estado HTTP.
        """
        try:
            # Añadir el cliente_id a los datos para que el modelo lo guarde
            datos_json['cliente_id'] = cliente_id
            
            # Validar los datos con el esquema de Marshmallow
            datos_validados = self.schema.load(datos_json)
            
            # Llamar al modelo para crear el reclamo en la base de datos
            resultado = self.model.create(datos_validados)
            
            if resultado.get("success"):
                return resultado, 201  # 201 Creado
            else:
                return resultado, 400  # 400 Solicitud incorrecta

        except ValidationError as err:
            # Error de validación de Marshmallow
            return {"success": False, "errors": err.messages}, 400

        except Exception as e:
            # Captura de cualquier otro error inesperado
            return {"success": False, "error": f"Error interno del servidor: {str(e)}"}, 500

    def obtener_reclamos_por_cliente(self, cliente_id):
        """
        Obtiene todos los reclamos para un cliente específico.

        Args:
            cliente_id (int): El ID del cliente.
        
        Returns:
            tuple: Una tupla con un diccionario de respuesta y un código de estado HTTP.
        """
        
        
        resultado = self.model.obtener_por_cliente(cliente_id)
        
        if resultado.get("success"):
            return resultado, 200  # 200 OK
        else:
            return resultado, 500  # Error del servidor
