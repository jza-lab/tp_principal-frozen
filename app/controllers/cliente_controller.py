
from app.controllers.base_controller import BaseController
from app.models.cliente import ClienteModel
from app.schemas.cliente_schema import ClienteSchema
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ClienteController(BaseController):
    """Controlador para operaciones de Clientes"""

    def __init__(self):
        super().__init__()
        self.model = ClienteModel()
        self.schema = ClienteSchema()

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
        """Obtener lista de Clientes"""
        try:
            filtros = filtros or {}

            result = self.model.get_all(include_direccion=True, filtros=filtros)
            if not result['success']:
                return self.error_response(result['error'])
            
            datos = result['data']
            sorted_data = sorted(datos, key=lambda x: x.get('activo', False), reverse=True)

            serialized_data = self.schema.dump(sorted_data, many=True)
            return self.success_response(data=serialized_data)
        except Exception as e:
            logger.error(f"Error obteniendo clientes: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_cliente(self, cliente_id: int) -> tuple:
        """Obtener un Cliente por su ID"""
        try:
            result = self.model.find_by_id(cliente_id, include_direccion=True)
            if not result['success']:
                return self.error_response(result['error'], 404)
            
            serialized_data = self.schema.dump(result['data'])
            print(serialized_data)

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
            direccion_data = data.pop('direccion', None)
            data['codigo'] = self.generar_codigo_unico()
            validated_data = self.schema.load(data)
            
            
            if validated_data.get('email'):
                respuesta, _ = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro cliente', 400)
            
            if validated_data.get('cuit'):
                respuesta, _ = self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
                    return self.error_response('El CUIT/CUIL ya está registrado para otro cliente', 400)
            
            direccion_id = self._get_or_create_direccion(direccion_data)
            if direccion_id:
                validated_data['direccion_id'] = direccion_id

            result = self.model.create(validated_data)

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
                respuesta, _ = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro cliente', 400)

            if validated_data.get('cuit') and validated_data['cuit'] != existing['data'].get('cuit'):
                respuesta, _ = self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
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