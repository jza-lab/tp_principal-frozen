from app.controllers.base_controller import BaseController
from app.controllers.registro_controller import RegistroController
from app.models.cliente import ClienteModel
from app.schemas.cliente_schema import ClienteSchema
from flask_jwt_extended import get_current_user
from app.controllers.pedido_controller import PedidoController
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Dict, Optional
import logging


logger = logging.getLogger(__name__)

class ClienteController(BaseController):
    """Controlador para operaciones de Clientes"""

    def __init__(self):
        super().__init__()
        self.model = ClienteModel()
        self.schema = ClienteSchema()
        self.pedido_controller=PedidoController()
        self.registro_controller = RegistroController()

    def obtener_clientes_activos(self) -> tuple:
        """Obtener lista de Clientes activos"""
        try:
            result = self.model.get_all_activos(include_direccion=True)
            if not result['success']:
                return self.error_response(result['error'])
            serialized_data = self.schema.dump(result['data'], many=True)
            return self.success_response(data=serialized_data)
        except Exception as e:
            logger.error(f"Error obteniendo Clientes: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_clientes(self, filtros: Optional[Dict] = None) -> tuple:
        """Obtener lista de Clientees activos"""
        try:
            filtros = filtros or {}
            # Pasar los filtros, incluyendo 'busqueda', al modelo
            result = self.model.get_all(filtros=filtros) 

            if not result['success']:
                return self.error_response(result['error'])

            datos = result['data']
            sorted_data = sorted(datos, key=lambda x: x.get('activo', False), reverse=True)

            serialized_data = self.schema.dump(sorted_data, many=True)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo clientees: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_cliente(self, cliente_id: int) -> tuple:
        """Obtener un Cliente por su ID"""
        try:
            result = self.model.find_by_id(cliente_id, include_direccion=True)
            if not result['success']:
                return self.error_response(result['error'], 404)
            
            serialized_data = self.schema.dump(result['data'])

            return self.success_response(data=serialized_data)
        except Exception as e:
            logger.error(f"Error obteniendo Cliente {cliente_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_cliente_cuil(self, cliente_cuil: str) -> tuple:
        """Obtener un Cliente por su ID"""
        try:
            result = self.model.buscar_por_cuit(cliente_cuil, include_direccion=True)
            if not result['success']:
                return self.error_response(result['error'], 404)
            
            serialized_data = self.schema.dump(result['data'])
            return self.success_response(data=result['data'])
        except Exception as e:
            logger.error(f"Error obteniendo Cliente {cliente_cuil}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def eliminar_cliente(self, cliente_id: int) -> tuple:
        """Elimina (desactiva) un Cliente por su ID"""
        try:
            existing = self.model.find_by_id(cliente_id)
            if not existing.get('success'):
                return self.error_response('Cliente no encontrado', 404)
            resultado_actualizar = self.model.update(cliente_id, {'activo': False}, 'id')
            if not resultado_actualizar.get('success'):
                return self.error_response(resultado_actualizar.get('error', 'Error al desactivar el Cliente'))
            
            cliente = existing.get('data')
            detalle = f"Se eliminó lógicamente al cliente '{cliente.get('razon_social') or cliente.get('nombre')}' (CUIT: {cliente.get('cuit')})."
            self.registro_controller.crear_registro(get_current_user(), 'Clientes', 'Eliminación Lógica', detalle)
            return self.success_response(message='Cliente desactivado exitosamente')
        except Exception as e:
            logger.error(f"Error eliminando Cliente {cliente_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)
        
    def habilitar_cliente(self, cliente_id: int) -> tuple:
        """Habilita (activa) un Cliente por su ID"""
        try:
            existing = self.model.find_by_id(cliente_id)
            if not existing.get('success'):
                return self.error_response('Cliente no encontrado', 404)
            resultado_actualizar = self.model.update(cliente_id, {'activo': True}, 'id')
            if not resultado_actualizar.get('success'):
                return self.error_response(resultado_actualizar.get('error', 'Error al activar el cliente'))
            return self.success_response(message='Cliente activado exitosamente')
        except Exception as e:
            logger.error(f"Error habilitando cliente {cliente_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def generate_random_int(self, start: int, end: int) -> int:
        import random
        return random.randint(start, end)

    def generar_codigo_unico(self) -> str:
        try:
            while True:
                codigo = f"CLTE-{self.generate_random_int(1000, 9999)}"
                existing = self.model.db.table(self.model.get_table_name()).select("id").eq("codigo", codigo).execute()
                if not existing.data:
                    return codigo
        except Exception as e:
            logger.error(f"Error generando código único para Cliente: {str(e)}")
            raise

    def crear_cliente(self, data: Dict) -> tuple:
        
        try:
            data.pop('csrf_token', None)
            direccion_data = data.pop('direccion', None)
            data['codigo'] = self.generar_codigo_unico()
            es_email_empresarial = data.pop('email_empresarial', False)
            contrasena = data.get('contrasena')
            if contrasena:
                data['contrasena'] = generate_password_hash(contrasena)
            else:
                return self.error_response('La contraseña es obligatoria', 400)
            
            if data.get('email'):
                respuesta= self.model.buscar_por_email(data['email'])
                
                if respuesta.get('success'):
                    return self.error_response('El email ya está registrado para otro cliente', 400)

            if data.get('cuit'):
                respuesta= self.model.buscar_por_cuit(data['cuit'])
                
                if respuesta.get('success'):
                    if es_email_empresarial and not data.get('razon_social'):
                        return self.error_response('La Razón Social es obligatoria al registrar un email empresarial con un CUIT ya existente.', 400)
                    if not es_email_empresarial:
                        return self.error_response('El CUIT/CUIL ya está registrado para otro cliente.', 400)
                    email = data.get('email')
                    if not email or '@' not in email:
                        return self.error_response('Email inválido para la validación de email empresarial.', 400)
                    
                    nuevo_dominio = email.split('@')[1]
                    clientes_existentes = respuesta.get('data', [])
                    primer_cliente_email = clientes_existentes[0].get('email')

                    if not primer_cliente_email or '@' not in primer_cliente_email:
                        return self.error_response('El cliente existente con este CUIT no tiene un email válido para comparar.', 400)

                    dominio_existente = primer_cliente_email.split('@')[1]

                    # Verificamos que todos los clientes existentes con ese CUIT usen el mismo dominio.
                    for cliente in clientes_existentes:
                        email_actual = cliente.get('email')
                        if not email_actual or '@' not in email_actual or email_actual.split('@')[1] != dominio_existente:
                            return self.error_response(f"Inconsistencia de datos: Múltiples dominios de email para el CUIT {data['cuit']}. Contacte a soporte.", 409)

                    # Comparamos el dominio del nuevo email con el dominio ya registrado para ese CUIT.
                    if nuevo_dominio.lower() != dominio_existente.lower():
                        return self.error_response(
                            f'El dominio del email ({nuevo_dominio}) no coincide con el dominio empresarial ya registrado para este CUIT.',
                            400
                        )
            data['estado_aprobacion'] = 'pendiente'
            direccion_id = self._get_or_create_direccion(direccion_data)
            if direccion_id:
                data['direccion_id'] = direccion_id
            
            if 'email_empresarial' in data:
                del data['email_empresarial']

            result = self.model.create(data)

            if result['success']:
                cliente = result.get('data')
                detalle = f"Se creó el cliente '{cliente.get('razon_social') or cliente.get('nombre')}' (CUIT: {cliente.get('cuit')})."
                self.registro_controller.crear_registro(get_current_user(), 'Clientes', 'Creación', detalle)
                return self.success_response(data=cliente, message='Cliente creado exitosamente', status_code=201)
            else:
                return self.error_response(result.get('error', 'Error al crear el cliente'), 500)

        except Exception as e:
            logger.error(f"Error creando cliente: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)
    
    def actualizar_cliente(self, cliente_id: int, data: Dict) -> tuple:
        try:
            existing = self.model.find_by_id(cliente_id)
            if not existing.get('success'):
                return self.error_response('Cliente no encontrado', 404)

            direccion_data = data.pop('direccion', None)
            data.pop('contrasena', None)
            data.pop('email_empresarial', None)
            validated_data = self.schema.load(data, partial=True)

            if validated_data.get('email') and validated_data['email'] != existing['data'].get('email'):
                respuesta= self.model.buscar_por_email(validated_data['email'])
                if respuesta.get('success'):
                    return self.error_response('El email ya está registrado para otro cliente', 400)

            if validated_data.get('cuit') and validated_data['cuit'] != existing['data'].get('cuit'):
                respuesta= self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta.get('success'):
                    return self.error_response('El CUIT/CUIL ya está registrado para otro cliente', 400)

            if direccion_data:
                id_direccion_vieja = existing['data'].get('direccion_id')
                
                if id_direccion_vieja:
                    cantidad_misma_direccion = self.model.contar_clientes_direccion(id_direccion_vieja)
                    
                    if cantidad_misma_direccion > 1:
                        id_nueva_direccion = self._get_or_create_direccion(direccion_data)
                        if id_nueva_direccion:
                            validated_data['direccion_id'] = id_nueva_direccion
                    else: 
                        self._actualizar_direccion(id_direccion_vieja, direccion_data)
                else:
                    id_nueva_direccion = self._get_or_create_direccion(direccion_data)
                    if id_nueva_direccion:
                        validated_data['direccion_id'] = id_nueva_direccion

            update_result = self.model.update(cliente_id, validated_data, 'id')
            if not update_result.get('success'):
                return self.error_response(update_result.get('error', 'Error al actualizar el Cliente'))

            result = self.model.find_by_id(cliente_id, include_direccion=True)
            if result.get('success'):
                cliente = result.get('data')
                detalle = f"Se actualizó el cliente '{cliente.get('razon_social') or cliente.get('nombre')}' (CUIT: {cliente.get('cuit')})."
                self.registro_controller.crear_registro(get_current_user(), 'Clientes', 'Actualización', detalle)
                serialized_data = self.schema.dump(cliente)
                return self.success_response(data=serialized_data, message='Cliente actualizado exitosamente')
            else:
                return self.error_response('Error al obtener el Cliente actualizado', 500)

        except Exception as e:
            logger.error(f"Error actualizando Cliente {cliente_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)
        

    def buscar_cliente_por_cuit_y_email(self, cuit, email) -> Dict:
        """
        Busca un cliente por CUIT y Email.
        """
            # 1. Buscar por CUIT
        cuit_result = self.model.buscar_por_cuit(cuit, include_direccion=True)
            
        if not cuit_result.get('success') or not cuit_result.get('data'):
            return self.error_response('Cliente no encontrado con ese CUIL/CUIT.', 404)

            # 2. Asumimos que buscar_por_cuit devuelve una lista (aunque sea de 1 elemento)
        cliente_encontrado = cuit_result['data'][0]
            
            # 3. Validar coincidencia de Email
        if cliente_encontrado.get('email', '').strip().lower() != email.strip().lower():
            return self.error_response('El Email ingresado no coincide con el Email de contacto registrado para ese CUIL/CUIT.', 401)
            
            # 4. Serializar y devolver (usando el esquema para incluir la dirección anidada)
        serialized_data = self.schema.dump(cliente_encontrado)

        return self.success_response(data=serialized_data)
    
    def verificar_credenciales_cliente(self, cuit: str, email: str) -> tuple:
        """
        Verifica las credenciales (CUIT y Email) de un cliente para el login.
        """
        try:
            cuit_result = self.model.buscar_por_cuit(cuit, include_direccion=True)
            
            if not cuit_result.get('success') or not cuit_result.get('data'):
                return self.error_response('Cliente no encontrado.', 404)

            cliente_encontrado = cuit_result['data'][0]
            
            if cliente_encontrado.get('email', '').strip().lower() != email.strip().lower():
                return self.error_response('Credenciales incorrectas.', 401)
            
            serialized_data = self.schema.dump(cliente_encontrado)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error verificando credenciales para CUIT {cuit}: {str(e)}")
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def cliente_tiene_pedidos_previos(self, cliente_id: int) -> bool:
        """
        Verifica si un cliente tiene pedidos anteriores.
        """
        from app.models.pedido import PedidoModel
        pedido_model = PedidoModel()
        
        try:
            # Buscamos pedidos que NO estén cancelados.
            pedidos_result , _ = self.pedido_controller.obtener_pedidos(filtros={'id_cliente': cliente_id})
            
            if pedidos_result.get('success') and pedidos_result.get('data'):
                # Filtramos para asegurarnos de que no sean solo pedidos 'CANCELADO'
                pedidos_validos = [p for p in pedidos_result['data'] if p.get('estado') != 'CANCELADO']
                return len(pedidos_validos) > 0
            return False
        except Exception as e:
            logger.error(f"Error verificando pedidos previos para cliente {cliente_id}: {str(e)}")
            return False
    
    
    def autenticar_cliente(self, email: str, contrasena: str) -> tuple:
        """
        Autentica a un cliente por CUIT y contraseña.
        """
        try:
            email_result = self.model.buscar_por_email(email, include_direccion=True)

            if email_result.get('estado_aprobacion') == 'rechazado':
                return self.error_response('La validez de los datos de este cliente fue rechazada por administración.', 400)

            if not email_result.get('success') or not email_result.get('data'):
                return self.error_response('Credenciales incorrectas.', 401)
            
            cliente_encontrado = email_result['data'][0]

            if not check_password_hash(cliente_encontrado.get('contrasena', ''), contrasena):
                return self.error_response('Credenciales incorrectas.', 401)
            
            cliente_encontrado.pop('contrasena', None)
            
            serialized_data = self.schema.dump(cliente_encontrado)
            
            if 'email' not in serialized_data:
                serialized_data['email'] = email # Usamos el email de la entrada del login, que es el correcto.

            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error durante la autenticación del cliente: {str(e)}")
            return self.error_response('Error interno del servidor.', 500)

    def actualizar_estado_cliente(self, cliente_id: int, nuevo_estado: str) -> tuple:
        """
        Actualiza el estado de aprobación de un cliente.
        """
        try:
            estados_validos = ['aprobado', 'rechazado', 'pendiente']
            if nuevo_estado not in estados_validos:
                return self.error_response(f'Estado no válido. Los estados permitidos son: {", ".join(estados_validos)}.', 400)

            existing = self.model.find_by_id(cliente_id)
            if not existing.get('success'):
                return self.error_response('Cliente no encontrado', 404)

            update_data = {'estado_aprobacion': nuevo_estado}
            resultado_actualizar = self.model.update(cliente_id, update_data, 'id')

            if not resultado_actualizar.get('success'):
                return self.error_response(resultado_actualizar.get('error', 'Error al actualizar el estado del cliente'))

            return self.success_response(message='Estado del cliente actualizado exitosamente')

        except Exception as e:
            logger.error(f"Error actualizando estado del cliente {cliente_id}: {str(e)}")
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)

    def obtener_conteo_clientes_pendientes(self) -> tuple:
        """
        Obtiene el número de clientes con estado de aprobación 'pendiente'.
        """
        try:
            result = self.model.get_count(filtros={'estado_aprobacion': 'pendiente'})
            if not result['success']:
                return self.error_response(result['error'])
            
            return self.success_response(data={'count': result['data']})
        except Exception as e:
            logger.error(f"Error contando clientes pendientes: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)
        

    def obtener_perfil_cliente(self, cliente_id: int) -> tuple:
        """
        Obtiene el perfil completo de un cliente, incluyendo sus pedidos.
        """
        try:
            # 1. Obtener los datos del cliente
            cliente_response, status_code = self.obtener_cliente(cliente_id)
            if status_code != 200:
                return self.error_response('Cliente no encontrado', 404)

            cliente_data = cliente_response.get('data', {})

            # 2. Obtener los pedidos del cliente
            pedidos_response, _ = self.pedido_controller.obtener_pedidos_por_cliente(cliente_id)
            
            pedidos_data = []
            if pedidos_response.get('success'):
                pedidos_data = pedidos_response.get('data', [])

            # 3. Combinar los datos
            perfil_completo = cliente_data
            perfil_completo['pedidos'] = pedidos_data
            
            return self.success_response(data=perfil_completo)

        except Exception as e:
            logger.error(f"Error obteniendo el perfil del cliente {cliente_id}: {str(e)}")
            return self.error_response('Error interno del servidor.', 500)
