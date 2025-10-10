from app.controllers.base_controller import BaseController
from app.models.proveedor import ProveedorModel
from app.schemas.proveedor_schema import ProveedorSchema
from app.models.direccion import DireccionModel
from app.schemas.direccion_schema import DireccionSchema
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ProveedorController(BaseController):
    """Controlador para operaciones de proveedores"""

    def __init__(self):
        super().__init__()
        self.model = ProveedorModel()
        self.schema = ProveedorSchema()
        self.direccion_model = DireccionModel()
        self.direccion_schema = DireccionSchema()

    def _get_or_create_direccion(self, direccion_data: Dict) -> Optional[int]:
        """Busca una dirección existente o crea una nueva si no se encuentra."""
        if not direccion_data:
            return None

        validated_address = self.direccion_schema.load(direccion_data)

        existing_address_result = self.direccion_model.find_by_full_address(
            calle=validated_address['calle'],
            altura=validated_address['altura'],
            piso=validated_address.get('piso'),
            depto=validated_address.get('depto'),
            localidad=validated_address['localidad'],
            provincia=validated_address['provincia']
        )

        if existing_address_result['success']:
            return existing_address_result['data']['id']
        else:
            new_address_result = self.direccion_model.create(validated_address)
            if new_address_result['success']:
                return new_address_result['data']['id']
        return None

    def obtener_proveedores_activos(self) -> tuple:
        """Obtener lista de proveedores activos"""
        try:
            result = self.model.get_all_activos(include_direccion=True)
            if not result['success']:
                return self.error_response(result['error'])
            serialized_data = self.schema.dump(result['data'], many=True)
            return self.success_response(data=serialized_data)
        except Exception as e:
            logger.error(f"Error obteniendo proveedores: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_proveedores(self) -> tuple:
        """Obtener lista de proveedores"""
        try:
            result = self.model.get_all(include_direccion=True)
            if not result['success']:
                return self.error_response(result['error'])
            
            datos = result['data']
            sorted_data = sorted(datos, key=lambda x: x.get('activo', False), reverse=True)

            serialized_data = self.schema.dump(sorted_data, many=True)
            return self.success_response(data=serialized_data)
        except Exception as e:
            logger.error(f"Error obteniendo proveedores: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_proveedor(self, proveedor_id: int) -> tuple:
        """Obtener un proveedor por su ID"""
        try:
            result = self.model.find_by_id(proveedor_id, include_direccion=True)
            if not result['success']:
                return self.error_response(result['error'], 404)
            serialized_data = self.schema.dump(result['data'])
            return self.success_response(data=serialized_data)
        except Exception as e:
            logger.error(f"Error obteniendo proveedor {proveedor_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def eliminar_proveedor(self, proveedor_id: int) -> tuple:
        """Elimina (desactiva) un proveedor por su ID"""
        try:
            existing = self.model.find_by_id(proveedor_id)
            if not existing.get('success'):
                return self.error_response('Proveedor no encontrado', 404)
            resultado_actualizar = self.model.update(proveedor_id, {'activo': False}, 'id')
            if not resultado_actualizar.get('success'):
                return self.error_response(resultado_actualizar.get('error', 'Error al desactivar el proveedor'))
            return self.success_response(message='Proveedor desactivado exitosamente')
        except Exception as e:
            logger.error(f"Error eliminando proveedor {proveedor_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def habilitar_proveedor(self, proveedor_id: int) -> tuple:
        """Habilita (activa) un proveedor por su ID"""
        try:
            existing = self.model.find_by_id(proveedor_id)
            if not existing.get('success'):
                return self.error_response('Proveedor no encontrado', 404)
            resultado_actualizar = self.model.update(proveedor_id, {'activo': True}, 'id')
            if not resultado_actualizar.get('success'):
                return self.error_response(resultado_actualizar.get('error', 'Error al activar el proveedor'))
            return self.success_response(message='Proveedor activado exitosamente')
        except Exception as e:
            logger.error(f"Error habilitando proveedor {proveedor_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def generate_random_int(self, start: int, end: int) -> int:
        import random
        return random.randint(start, end)

    def generar_codigo_unico(self) -> str:
        try:
            while True:
                codigo = f"PRV-{self.generate_random_int(1000, 9999)}"
                existing = self.model.db.table(self.model.get_table_name()).select("id").eq("codigo", codigo).execute()
                if not existing.data:
                    return codigo
        except Exception as e:
            logger.error(f"Error generando código único para proveedor: {str(e)}")
            raise

    def crear_proveedor(self, data: Dict) -> tuple:
        try:
            direccion_data = data.pop('direccion', None)
            data['codigo'] = self.generar_codigo_unico()
            validated_data = self.schema.load(data)

            if validated_data.get('email'):
                respuesta, _ = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro proveedor', 400)

            if validated_data.get('cuit'):
                respuesta, _ = self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
                    return self.error_response('El CUIT/CUIL ya está registrado para otro proveedor', 400)

            direccion_id = self._get_or_create_direccion(direccion_data)
            if direccion_id:
                validated_data['direccion_id'] = direccion_id

            

            result = self.model.create(validated_data)

            if result['success']:
                return self.success_response(data=result['data'], message='Proveedor creado exitosamente', status_code=201)
            else:
                return self.error_response(result.get('error', 'Error al crear el proveedor'), 500)

        except Exception as e:
            logger.error(f"Error creando proveedor: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def actualizar_proveedor(self, proveedor_id: int, data: Dict) -> tuple:
        try:
            existing_result = self.model.find_by_id(proveedor_id)
            if not existing_result.get('success'):
                return self.error_response('Proveedor no encontrado', 404)

            existing_data = existing_result['data']
            direccion_data = data.pop('direccion', None)
            validated_data = self.schema.load(data, partial=True)

            if validated_data.get('email') and validated_data['email'] != existing_data.get('email'):
                respuesta, _ = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro proveedor', 400)

            if validated_data.get('cuit') and validated_data['cuit'] != existing_data.get('cuit'):
                respuesta, _ = self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
                    return self.error_response('El CUIT/CUIL ya está registrado para otro proveedor', 400)

            if direccion_data:
                direccion_id = self._get_or_create_direccion(direccion_data)
                if direccion_id:
                    validated_data['direccion_id'] = direccion_id

            update_result = self.model.update(proveedor_id, validated_data, 'id')
            if not update_result.get('success'):
                return self.error_response(update_result.get('error', 'Error al actualizar el proveedor'))

            result = self.model.find_by_id(proveedor_id, include_direccion=True)
            if result.get('success'):
                serialized_data = self.schema.dump(result['data'])
                return self.success_response(data=serialized_data, message='Proveedor actualizado exitosamente')
            else:
                return self.error_response('Error al obtener el proveedor actualizado', 500)

        except Exception as e:
            logger.error(f"Error actualizando proveedor {proveedor_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)



         # --- MÉTODO NUEVO A AÑADIR ---
    def buscar_por_identificacion(self, data: Dict) -> Optional[Dict]:
        """

        Busca un proveedor por CUIT/CUIL o por email.
        Ideal para encontrar proveedores desde un archivo externo.
        """
        # Las columnas en el Excel pueden llamarse 'cuil_proveedor' o 'cuit'
        cuit = data.get('cuil_proveedor') or data.get('cuit')
        if cuit:
            proveedor_result, _ = self.model.buscar_por_cuit(cuit)
            if proveedor_result:
                return proveedor_result # Devuelve el diccionario del proveedor

        # Si no se encontró por CUIT, intentar por email
        email = data.get('email_proveedor') or data.get('email')
        if email:
            proveedor_result, _ = self.model.buscar_por_email(email)
            if proveedor_result:
                return proveedor_result # Devuelve el diccionario del proveedor

        # Si no se encontró por ninguno de los dos métodos
        return None
    # --- FIN DEL MÉTODO NUEVO ---