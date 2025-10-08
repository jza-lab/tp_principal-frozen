from app.controllers.base_controller import BaseController
from app.models.proveedor import ProveedorModel
from app.schemas.proveedor_schema import ProveedorSchema
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ProveedorController(BaseController):
    """Controlador para operaciones de proveedores"""

    def __init__(self):
        super().__init__()
        self.model = ProveedorModel()
        self.schema = ProveedorSchema()

    def obtener_proveedores_activos(self) -> tuple:
        """Obtener lista de proveedores activos"""
        try:
            result = self.model.get_all_activos()

            if not result['success']:
                return self.error_response(result['error'])

            serialized_data = self.schema.dump(result['data'], many=True)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo proveedores: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_proveedores(self) -> tuple:
        """Obtener lista de proveedores activos"""
        try:
            result = self.model.get_all()

            if not result['success']:
                return self.error_response(result['error'])

            serialized_data = self.schema.dump(result['data'], many=True)
            return self.success_response(data=serialized_data)

        except Exception as e:
            logger.error(f"Error obteniendo proveedores: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def obtener_proveedor(self, proveedor_id: int) -> tuple:
        """Obtener un proveedor por su ID"""
        try:
            result = self.model.find_by_id(proveedor_id, 'id')

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
            # Verificar si el proveedor existe
            existing = self.model.find_by_id(proveedor_id, 'id')
            if not existing.get('success') or not existing.get('data'):
                return self.error_response('Proveedor no encontrado', 404)

            # Actualizar el campo 'activo' a False
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
            # Verificar si el proveedor existe
            existing = self.model.find_by_id(proveedor_id, 'id')
            if not existing.get('success') or not existing.get('data'):
                return self.error_response('Proveedor no encontrado', 404)

            # Actualizar el campo 'activo' a True
            resultado_actualizar = self.model.update(proveedor_id, {'activo': True}, 'id')
            if not resultado_actualizar.get('success'):
                return self.error_response(resultado_actualizar.get('error', 'Error al activar el proveedor'))

            return self.success_response(message='Proveedor activado exitosamente')

        except Exception as e:
            logger.error(f"Error habilitando proveedor {proveedor_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def buscar_por_identificacion(self, fila: Dict) -> Optional[Dict]:
        """
        Busca proveedor por email o CUIL/CUIT usando el modelo

        Args:
            fila: Diccionario con datos que pueden contener email_proveedor o cuil_proveedor

        Returns:
            Dict con datos del proveedor o None
        """
        try:
            # Usar el método del modelo para buscar
            return self.model.buscar_por_identificacion(fila)

        except Exception as e:
            logger.error(f"Error en controlador buscando proveedor: {str(e)}")
            return None

    def generate_random_int(self, start: int, end: int) -> int:
        """Genera un número entero aleatorio entre start y end"""
        import random
        return random.randint(start, end)

    def generar_codigo_unico(self) -> str:
        """Genera un código único para un proveedor"""
        try:
            while True:
                codigo = f"PRV-{self.generate_random_int(1000, 9999)}"
                # Verificar que el código no exista ya
                existing = self.model.db.table(self.model.get_table_name()).select("id").eq("codigo", codigo).execute()
                if not existing.data:
                    return codigo
        except Exception as e:
            logger.error(f"Error generando código único para proveedor: {str(e)}")
            raise

    def crear_proveedor(self, data: Dict) -> tuple:
        """Crea un nuevo proveedor"""
        try:
            data['codigo'] = self.generar_codigo_unico()
            # Validar y limpiar datos
            validated_data = self.schema.load(data)
            if( validated_data.get('email') ):
                respuesta, estado = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro proveedor', 400)
            
            if( validated_data.get('cuit') ):
                respuesta, estado = self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
                    return self.error_response('El CUIT/CUIL ya está registrado para otro proveedor', 400)
            
            # Insertar en la base de datos
            result = self.model.db.table(self.model.get_table_name()).insert(validated_data).execute()

            if result.data:
                return self.success_response(data=result.data[0], message='Proveedor creado exitosamente', status_code=201)
            else:
                return self.error_response('Error al crear el proveedor', 500)

        except Exception as e:
            logger.error(f"Error creando proveedor: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)
    
    def actualizar_proveedor(self, proveedor_id: int, data: Dict) -> tuple:
        try:
            # Validar y limpiar datos
            validated_data = self.schema.load(data, partial=True)

            # Verificar si el proveedor existe
            existing = self.model.find_by_id(proveedor_id, 'id')
            if not existing.get('success') or not existing.get('data'):
                return self.error_response('Proveedor no encontrado', 404)

            # Si se está actualizando el email o CUIT, verificar unicidad
            if validated_data.get('email') and validated_data['email'] != existing['data']['email']:
                respuesta = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro proveedor', 400)

            if validated_data.get('cuit') and validated_data['cuit'] != existing['data']['cuit']:
                respuesta = self.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
                    return self.error_response('El CUIT/CUIL ya está registrado para otro proveedor', 400)

            # Actualizar en la base de datos
            update_result = self.model.update(proveedor_id, validated_data, 'id')
            if not update_result.get('success'):
                return self.error_response(update_result.get('error', 'Error al actualizar el proveedor'))

            # Obtener el proveedor actualizado
            result = self.model.find_by_id(proveedor_id, 'id')
            if result.get('success'):
                serialized_data = self.schema.dump(result['data'])
                return self.success_response(data=serialized_data, message='Proveedor actualizado exitosamente')
            else:
                return self.error_response('Error al obtener el proveedor actualizado', 500)

        except Exception as e:
            logger.error(f"Error actualizando proveedor {proveedor_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)