from app.controllers.base_controller import BaseController
from app.controllers.registro_controller import RegistroController
from app.models.proveedor import ProveedorModel
from app.schemas.proveedor_schema import ProveedorSchema
from flask_jwt_extended import get_current_user
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ProveedorController(BaseController):
    """Controlador para operaciones de proveedores"""

    def __init__(self):
        super().__init__()
        self.model = ProveedorModel()
        self.schema = ProveedorSchema()
        self.registro_controller = RegistroController()

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

    def obtener_proveedores(self, filtros: Optional[Dict] = None) -> tuple: # <-- ACEPTA FILTROS
        """Obtener lista de proveedores"""
        try:
            filtros = filtros or {} # Inicializar si es None
            # Pasar los filtros, incluyendo 'busqueda', al modelo
            result = self.model.get_all(include_direccion=True, filtros=filtros)
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

    def obtener_proveedor_cuil(self, proveedor_cuil: str) -> tuple:
        """Obtener un proveedor por su ID"""
        try:
            result = self.model.buscar_por_cuit(proveedor_cuil, include_direccion=True)
            if not result['success']:
                return self.error_response(result['error'], 404)

            serialized_data = self.schema.dump(result['data'])
            return self.success_response(data=result['data'])
        except Exception as e:
            logger.error(f"Error obteniendo proveedor {proveedor_cuil}: {str(e)}")
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
            
            proveedor = existing.get('data')
            detalle = f"Se eliminó lógicamente al proveedor '{proveedor.get('nombre')}' (CUIT: {proveedor.get('cuit')})."
            self.registro_controller.crear_registro(get_current_user(), 'Proveedores', 'Eliminación Lógica', detalle)
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
                respuesta= self.model.buscar_por_email(validated_data['email'])
                if respuesta.get('success'):
                    return self.error_response('El email ya está registrado para otro proveedor', 400)

            if validated_data.get('cuit'):
                respuesta = self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta.get('success'):
                    return self.error_response('El CUIT/CUIL ya está registrado para otro proveedor', 400)

            direccion_id = self._get_or_create_direccion(direccion_data)
            if direccion_id:
                validated_data['direccion_id'] = direccion_id

            result = self.model.create(validated_data)

            if result['success']:
                proveedor = result.get('data')
                detalle = f"Se creó el proveedor '{proveedor.get('nombre')}' (CUIT: {proveedor.get('cuit')})."
                self.registro_controller.crear_registro(get_current_user(), 'Proveedores', 'Creación', detalle)
                return self.success_response(data=proveedor, message='Proveedor creado exitosamente', status_code=201)
            else:
                return self.error_response(result.get('error', 'Error al crear el proveedor'), 500)

        except Exception as e:
            logger.error(f"Error creando proveedor: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)

    def actualizar_proveedor(self, proveedor_id: int, data: Dict) -> tuple:
        try:
            existing = self.model.find_by_id(proveedor_id)
            if not existing.get('success'):
                return self.error_response('Proveedor no encontrado', 404)


            direccion_data = data.pop('direccion', None)
            validated_data = self.schema.load(data, partial=True)

            if validated_data.get('email') and validated_data['email'] != existing['data'].get('email'):
                respuesta, _ = self.model.buscar_por_email(validated_data['email'])
                if respuesta:
                    return self.error_response('El email ya está registrado para otro proveedor', 400)

            if validated_data.get('cuit') and validated_data['cuit'] != existing['data'].get('cuit'):
                respuesta, _ = self.model.buscar_por_cuit(validated_data['cuit'])
                if respuesta:
                    return self.error_response('El CUIT/CUIL ya está registrado para otro proveedor', 400)

            if direccion_data:

                # 1. Obtener el ID de la dirección que el proveedor tiene ANTES de la actualización.
                id_direccion_vieja = existing['data'].get('direccion_id')

                if id_direccion_vieja:
                    cantidad_misma_direccion = self.model.contar_proveedores_direccion(id_direccion_vieja)

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


            update_result = self.model.update(proveedor_id, validated_data, 'id')
            if not update_result.get('success'):
                return self.error_response(update_result.get('error', 'Error al actualizar el proveedor'))

            result = self.model.find_by_id(proveedor_id, include_direccion=True)
            if result.get('success'):
                proveedor = result.get('data')
                detalle = f"Se actualizó el proveedor '{proveedor.get('nombre')}' (CUIT: {proveedor.get('cuit')})."
                self.registro_controller.crear_registro(get_current_user(), 'Proveedores', 'Actualización', detalle)
                serialized_data = self.schema.dump(proveedor)
                return self.success_response(data=serialized_data, message='Proveedor actualizado exitosamente')
            else:
                return self.error_response('Error al obtener el proveedor actualizado', 500)

        except Exception as e:
            logger.error(f"Error actualizando proveedor {proveedor_id}: {str(e)}")
            return self.error_response(f'Error interno: {str(e)}', 500)



    def buscar_por_identificacion(self, data: Dict) -> Optional[Dict]:
        """
        Busca un proveedor por CUIT/CUIL o por email y devuelve un único diccionario con los datos del proveedor.
        """
        cuit = data.get('cuil_proveedor') or data.get('cuit')
        if cuit:
            # --- CORRECCIÓN ---
            # El modelo devuelve un diccionario: {'success': True, 'data': [{...}]}
            proveedor_respuesta = self.model.buscar_por_cuit(cuit)

            # Verificamos si la búsqueda fue exitosa y si se encontraron datos
            if proveedor_respuesta.get('success') and proveedor_respuesta.get('data'):
                # Devolvemos el primer diccionario de la lista de datos
                return proveedor_respuesta['data'][0]
            # ------------------

        email = data.get('email_proveedor') or data.get('email')
        if email:
            # --- CORRECCIÓN (misma lógica para el email) ---
            proveedor_respuesta = self.model.buscar_por_email(email)
            if proveedor_respuesta.get('success') and proveedor_respuesta.get('data'):
                return proveedor_respuesta['data'][0]
            # ------------------

        # Si no se encontró por ninguno de los dos métodos
        return None