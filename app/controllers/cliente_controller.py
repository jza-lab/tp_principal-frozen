
from app.controllers.base_controller import BaseController
from app.models.cliente import ClienteModel
from app.schemas.cliente_schema import ClienteSchema
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
            
            if data.get('email'):
                respuesta= self.model.buscar_por_email(data['email'])
                
                if respuesta.get('success'):
                    return self.error_response('El email ya está registrado para otro cliente', 400)
            
            if data.get('cuit'):
                respuesta= self.model.buscar_por_cuit(data['cuit'])
                
                if respuesta.get('success'):
                    return self.error_response('El CUIT/CUIL ya está registrado para otro cliente', 400)
            
            direccion_id = self._get_or_create_direccion(direccion_data)
            if direccion_id:
                data['direccion_id'] = direccion_id

            result = self.model.create(data)

            if result['success']:
                return self.success_response(data=result['data'], message='Cliente creado exitosamente', status_code=201)
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
                serialized_data = self.schema.dump(result['data'])
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
    
    
    def autenticar_cliente(self, cuit: str, contrasena: str) -> tuple:
        """
        Autentica a un cliente por CUIT y contraseña.
        """
        try:
            cuit_result = self.model.buscar_por_cuit(cuit, include_direccion=True)
            
            if not cuit_result.get('success') or not cuit_result.get('data'):
                return self.error_response('Credenciales incorrectas.', 401)

            cliente_encontrado = cuit_result['data'][0]
            
            if not check_password_hash(cliente_encontrado.get('contrasena', ''), contrasena):
                return self.error_response('Credenciales incorrectas.', 401)
            
            # No devolver el hash de la contraseña
            cliente_encontrado.pop('contrasena', None)
            
            serialized_data = self.schema.dump(cliente_encontrado)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error en la autenticación para CUIT {cuit}: {str(e)}")
            return self.error_response(f'Error interno del servidor: {str(e)}', 500)