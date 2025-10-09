from app.controllers.base_controller import BaseController
from app.models.cliente import ClienteModel
from app.schemas.cliente_schema import ClienteSchema
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ClienteController(BaseController):
    """Controlador para operaciones de Clientees"""

    def __init__(self):
        super().__init__()
        self.model = ClienteModel()
        self.schema = ClienteSchema()

    def obtener_clientees_activos(self) -> tuple:
        """Obtener lista de Clientees activos"""
        try:
            result = self.model.get_all_activos()

            if not result['success']:
                return self.error_response(result['error'])

            serialized_data = self.schema.dump(result['data'], many=True)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo Clientees: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_clientes(self) -> tuple:
        """Obtener lista de Clientees activos"""
        try:
            result = self.model.get_all()

            if not result['success']:
                return self.error_response(result['error'])

            serialized_data = self.schema.dump(result['data'], many=True)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo clientees: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_cliente(self, cliente_id: int) -> tuple:
        """Obtener un Cliente por su ID"""
        try:
            result = self.model.find_by_id(cliente_id, 'id')

            if not result['success']:
                return self.error_response(result['error'], 404)

            serialized_data = self.schema.dump(result['data'])
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo Cliente {cliente_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def eliminar_cliente(self, cliente_id: int) -> tuple:
        """Elimina (desactiva) un Cliente por su ID"""
        try:
            # Verificar si el Cliente existe
            existing = self.model.find_by_id(cliente_id, 'id')
            if not existing.get('success') or not existing.get('data'):
                return self.error_response('Cliente no encontrado', 404)

            # Actualizar el campo 'activo' a False
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
            # Verificar si el Cliente existe
            existing = self.model.find_by_id(cliente_id, 'id')
            if not existing.get('success') or not existing.get('data'):
                return self.error_response('Cliente no encontrado', 404)

            # Actualizar el campo 'activo' a True
            resultado_actualizar = self.model.update(cliente_id, {'activo': True}, 'id')
            if not resultado_actualizar.get('success'):
                return self.error_response(resultado_actualizar.get('error', 'Error al activar el cliente'))

            return self.success_response(message='Cliente activado exitosamente')

        except Exception as e:
            logger.error(f"Error habilitando cliente {cliente_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def generate_random_int(self, start: int, end: int) -> int:
        """Genera un número entero aleatorio entre start y end"""
        import random
        return random.randint(start, end)

    def generar_codigo_unico(self) -> str:
        """Genera un código único para un Cliente"""
        try:
            while True:
                codigo = f"CLTE-{self.generate_random_int(1000, 9999)}"
                # Verificar que el código no exista ya
                existing = self.model.db.table(self.model.get_table_name()).select("id").eq("codigo", codigo).execute()
                if not existing.data:
                    return codigo
        except Exception as e:
            logger.error(f"Error generando código único para Cliente: {str(e)}")
            raise

    def crear_cliente(self, data: Dict) -> tuple:
        """Crea un nuevo Cliente"""
        try:
            data['codigo'] = self.generar_codigo_unico()
            # Validar y limpiar datos
            validated_data = self.schema.load(data)
            if( validated_data.get('email') ):
                respuesta, estado = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro cliente', 400)
            
            if( validated_data.get('cuit') ):
                respuesta, estado = self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
                    return self.error_response('El CUIT/CUIL ya está registrado para otro cliente', 400)
            
            # Insertar en la base de datos
            result = self.model.db.table(self.model.get_table_name()).insert(validated_data).execute()

            if result.data:
                return self.success_response(data=result.data[0], message='Cliente creado exitosamente', status_code=201)
            else:
                return self.error_response('Error al crear el cliente', 500)

        except Exception as e:
            logger.error(f"Error creando cliente: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)
    
    def actualizar_cliente(self, cliente_id: int, data: Dict) -> tuple:
        try:
            # Validar y limpiar datos
            validated_data = self.schema.load(data, partial=True)

            # Verificar si el Cliente existe
            existing = self.model.find_by_id(cliente_id, 'id')
            if not existing.get('success') or not existing.get('data'):
                return self.error_response('Cliente no encontrado', 404)

            # Si se está actualizando el email o CUIT, verificar unicidad
            if validated_data.get('email') and validated_data['email'] != existing['data']['email']:
                respuesta = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro Cliente', 400)

            if validated_data.get('cuit') and validated_data['cuit'] != existing['data']['cuit']:
                respuesta = self.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
                    return self.error_response('El CUIT/CUIL ya está registrado para otro Cliente', 400)

            # Actualizar en la base de datos
            update_result = self.model.update(cliente_id, validated_data, 'id')
            if not update_result.get('success'):
                return self.error_response(update_result.get('error', 'Error al actualizar el Cliente'))

            # Obtener el Cliente actualizado
            result = self.model.find_by_id(cliente_id, 'id')
            if result.get('success'):
                serialized_data = self.schema.dump(result['data'])
                return self.success_response(data=serialized_data, message='Cliente actualizado exitosamente')
            else:
                return self.error_response('Error al obtener el Cliente actualizado', 500)

        except Exception as e:
            logger.error(f"Error actualizando Cliente {cliente_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)