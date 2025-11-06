from app.models.reclamo import ReclamoModel
from app.models.reclamo_mensaje import ReclamoMensajeModel # Importar nuevo modelo
from app.schemas.reclamo_schema import ReclamoSchema
from app.schemas.reclamo_mensaje_schema import ReclamoMensajeSchema # Importar nuevo schema
from marshmallow import ValidationError
from flask_wtf import FlaskForm
import logging
from flask_jwt_extended import get_current_user
from app.controllers.registro_controller import RegistroController

logger = logging.getLogger(__name__)

class ReclamoController:
    """
    Controlador para gestionar la lógica de negocio de los reclamos.
    """
    def __init__(self):
        self.model = ReclamoModel()
        self.schema = ReclamoSchema()
        self.mensaje_model = ReclamoMensajeModel() # Nuevo
        self.mensaje_schema = ReclamoMensajeSchema() # Nuevo
        self.registro_controller = RegistroController()

    def crear_reclamo(self, datos_json, cliente_id):
            """
            Valida los datos de un nuevo reclamo y lo crea en la base de datos.
            """
            try:
                datos_json['cliente_id'] = cliente_id
                
                # --- INICIO DE LA CORRECCIÓN ---
                
                # 1. Capturamos el comentario inicial
                comentario_inicial = datos_json.get('comentarios', 'Reclamo iniciado sin comentarios.')
                if not comentario_inicial:
                    comentario_inicial = "Reclamo iniciado sin comentarios."

                # 2. Asignamos el comentario al campo 'comentarios' para que se guarde en la tabla 'reclamos'
                #    (Esto es lo que faltaba)
                datos_json['comentarios'] = comentario_inicial

                # 3. Validamos todo el payload (incluyendo el comentario que acabamos de asignar)
                datos_validados = self.schema.load(datos_json)
                
                # 4. Crear el reclamo principal (ahora 'datos_validados' tiene el comentario)
                resultado = self.model.create(datos_validados)
                
                # --- FIN DE LA CORRECCIÓN ---
                
                if not resultado.get("success"):
                    return resultado, 400

                nuevo_reclamo = resultado.get("data")
                
                # 5. Crear el primer mensaje (esto ya estaba bien)
                datos_mensaje = {
                    "reclamo_id": nuevo_reclamo['id'],
                    "cliente_id": cliente_id,
                    "mensaje": comentario_inicial
                }
                self.mensaje_model.create_mensaje(datos_mensaje)

                # Crear un usuario 'ficticio' para el registro
                from types import SimpleNamespace
                usuario_sistema = SimpleNamespace(nombre='Cliente', apellido='Externo', roles=['CLIENTE'])
                detalle = f"Se creó el reclamo N° {nuevo_reclamo['id']}."
                self.registro_controller.crear_registro(usuario_sistema, 'Reclamos', 'Creación', detalle)

                return resultado, 201  # 201 Creado

            except ValidationError as err:
                return {"success": False, "errors": err.messages}, 400
            except Exception as e:
                logger.error(f"Error al crear reclamo: {e}", exc_info=True)
                return {"success": False, "error": f"Error interno del servidor: {str(e)}"}, 500

 
    def obtener_reclamos_por_cliente(self, cliente_id):
        """
        Obtiene todos los reclamos para un cliente específico.
        """
        resultado = self.model.obtener_por_cliente(cliente_id)
        
        if resultado.get("success"):
            return resultado, 200
        else:
            return resultado, 500

    def obtener_reclamos_admin(self):
        """
        Obtiene todos los reclamos para el panel de administración.
        """
        resultado = self.model.find_all_admin()
        if resultado.get("success"):
            return resultado, 200
        else:
            return resultado, 500

    def obtener_detalle_reclamo(self, reclamo_id: int):
        """
        Obtiene el detalle de un reclamo, incluyendo sus mensajes.
        (La seguridad/verificación de ID se hace en la ruta)
        """
        resultado = self.model.find_by_id_con_mensajes(reclamo_id)
        if resultado.get("success"):
            return resultado, 200
        else:
            return resultado, 404

    def responder_reclamo_admin(self, reclamo_id: int, admin_usuario_id: int, mensaje: str):
        """
        Un administrador responde a un reclamo.
        Cambia el estado a 'respondida'.
        """
        try:
            # 1. Crear el mensaje
            datos_mensaje = {
                "reclamo_id": reclamo_id,
                "usuario_id": admin_usuario_id,
                "mensaje": mensaje
            }
            msg_result = self.mensaje_model.create_mensaje(datos_mensaje)
            if not msg_result.get("success"):
                return msg_result, 400
            
            # 2. Actualizar estado del reclamo principal
            estado_result = self.model.update_estado(reclamo_id, "respondida")
            if not estado_result.get("success"):
                return estado_result, 400
            
            detalle = f"El reclamo N° {reclamo_id} fue respondido por un administrador y cambió de estado a 'Respondida'."
            self.registro_controller.crear_registro(get_current_user(), 'Reclamos', 'Cambio de Estado', detalle)
                
            return {"success": True, "message": "Respuesta enviada."}, 201

        except Exception as e:
            logger.error(f"Error admin al responder reclamo {reclamo_id}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def responder_reclamo_cliente(self, reclamo_id: int, cliente_id: int, mensaje: str):
        """
        Un cliente responde a un reclamo.
        Cambia el estado a 'pendiente' (vuelve a la cola del admin).
        """
        try:
            # 1. Crear el mensaje
            datos_mensaje = {
                "reclamo_id": reclamo_id,
                "cliente_id": cliente_id,
                "mensaje": mensaje
            }
            msg_result = self.mensaje_model.create_mensaje(datos_mensaje)
            if not msg_result.get("success"):
                return msg_result, 400
            
            # 2. Actualizar estado del reclamo principal
            estado_result = self.model.update_estado(reclamo_id, "pendiente")
            if not estado_result.get("success"):
                return estado_result, 400
            
            from types import SimpleNamespace
            usuario_sistema = SimpleNamespace(nombre='Cliente', apellido='Externo', roles=['CLIENTE'])
            detalle = f"El reclamo N° {reclamo_id} fue respondido por el cliente y cambió de estado a 'Pendiente'."
            self.registro_controller.crear_registro(usuario_sistema, 'Reclamos', 'Cambio de Estado', detalle)
                
            return {"success": True, "message": "Respuesta enviada."}, 201

        except Exception as e:
            logger.error(f"Error cliente al responder reclamo {reclamo_id}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500

    def cerrar_reclamo_cliente(self, reclamo_id: int):
        """
        Un cliente marca un reclamo como 'solucionada'.
        """
        try:
            estado_result = self.model.update_estado(reclamo_id, "solucionada")
            if not estado_result.get("success"):
                return estado_result, 400
            
            from types import SimpleNamespace
            usuario_sistema = SimpleNamespace(nombre='Cliente', apellido='Externo', roles=['CLIENTE'])
            detalle = f"El reclamo N° {reclamo_id} fue cerrado por el cliente y cambió de estado a 'Solucionada'."
            self.registro_controller.crear_registro(usuario_sistema, 'Reclamos', 'Cambio de Estado', detalle)
                
            return {"success": True, "message": "Reclamo marcado como solucionado."}, 200
        except Exception as e:
            logger.error(f"Error al cerrar reclamo {reclamo_id}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500
            
    def cancelar_reclamo_admin(self, reclamo_id: int):
        """
        Un admin marca un reclamo como 'cancelado'.
        """
        try:
            estado_result = self.model.update_estado(reclamo_id, "cancelado")
            if not estado_result.get("success"):
                return estado_result, 400
            
            detalle = f"El reclamo N° {reclamo_id} fue cancelado por un administrador."
            self.registro_controller.crear_registro(get_current_user(), 'Reclamos', 'Cancelación', detalle)
                
            return {"success": True, "message": "Reclamo cancelado por administración."}, 200
        except Exception as e:
            logger.error(f"Error al cancelar reclamo {reclamo_id}: {e}", exc_info=True)
            return {"success": False, "error": f"Error interno: {str(e)}"}, 500