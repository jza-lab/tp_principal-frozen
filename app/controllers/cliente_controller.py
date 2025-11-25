from app.controllers.base_controller import BaseController
from app.controllers.registro_controller import RegistroController
from app.models.cliente import ClienteModel
from app.schemas.cliente_schema import ClienteSchema
from flask_jwt_extended import get_current_user
from app.controllers.pedido_controller import PedidoController
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Dict, Optional
import logging
from app.config import Config
from decimal import Decimal


logger = logging.getLogger(__name__)

class ClienteController(BaseController):
    """Controlador para operaciones de Clientes"""

    def __init__(self):
        super().__init__()
        from app.controllers.direccion_controller import GeorefController
        self.model = ClienteModel()
        self.schema = ClienteSchema()
        self.pedido_controller=PedidoController()
        self.registro_controller = RegistroController()
        self.usuario_direccion_controller = GeorefController()

    def _normalizar_y_preparar_direccion(self, direccion_data: Dict) -> Optional[Dict]:
        """Helper para normalizar una dirección usando un servicio externo."""
        if not all(direccion_data.get(k) for k in ['calle', 'altura', 'localidad', 'provincia']):
            return direccion_data

        full_street = f"{direccion_data['calle']} {direccion_data['altura']}"
        if direccion_data.get('piso'):
            full_street += f", Piso {direccion_data.get('piso')}"
        if direccion_data.get('depto'):
            full_street += f", Depto {direccion_data.get('depto')}"

        norm_result = self.usuario_direccion_controller.normalizar_direccion(
            direccion=full_street,
            localidad=direccion_data['localidad'],
            provincia=direccion_data['provincia']
        )

        if not norm_result.get('success'):
            return direccion_data

        norm_data = norm_result['data']
        return {
            "calle": norm_data['calle']['nombre'],
            "altura": norm_data['altura']['valor'],
            "piso": direccion_data.get('piso'),
            "depto": direccion_data.get('depto'),
            "codigo_postal": norm_data.get('codigo_postal', direccion_data.get('codigo_postal')),
            "localidad": norm_data['localidad_censal']['nombre'],
            "provincia": norm_data['provincia']['nombre'],
            "latitud": norm_data['ubicacion']['lat'],
            "longitud": norm_data['ubicacion']['lon']
        }

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

    def obtener_cliente_por_cuit(self, cuit: str) -> tuple:
        """Obtener un Cliente por su CUIT/CUIL"""
        return self.obtener_cliente_cuil(cuit)

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
            
            cliente = existing.get('data')
            detalle = f"Se habilitó al cliente '{cliente.get('razon_social') or cliente.get('nombre')}' (CUIT: {cliente.get('cuit')})."
            self.registro_controller.crear_registro(get_current_user(), 'Clientes', 'Habilitación', detalle)
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
            
            # Normalizar la dirección antes de crearla
            if direccion_data:
                direccion_data = self._normalizar_y_preparar_direccion(direccion_data)

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
                # Normalizar la dirección antes de actualizarla o crearla
                direccion_data = self._normalizar_y_preparar_direccion(direccion_data)
                
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
            
            cliente = existing.get('data')
            detalle = f"El estado de aprobación del cliente '{cliente.get('razon_social') or cliente.get('nombre')}' cambió a {nuevo_estado}."
            self.registro_controller.crear_registro(get_current_user(), 'Clientes', 'Cambio de Estado', detalle)
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
            
            pedidos_enriquecidos = []
            if pedidos_response.get('success'):
                from app.controllers.pago_controller import PagoController
                pago_controller = PagoController()
                pedidos_crudos = pedidos_response.get('data', [])
                for pedido_base in pedidos_crudos:
                    # Obtener el pedido completo, que ya incluye los items
                    pedido_completo_resp, _ = self.pedido_controller.obtener_pedido_por_id(pedido_base['id'])
                    if pedido_completo_resp.get('success'):
                        pedido = pedido_completo_resp.get('data')
                        
                        # Calcular saldo pendiente
                        pagos_res, _ = pago_controller.get_pagos_by_pedido_id(pedido['id'])
                        pagos_data = pagos_res.get('data', []) if isinstance(pagos_res, dict) else pagos_res[0].get('data', [])
                        total_pagado = sum(Decimal(p['monto']) for p in pagos_data)
                        precio_orden = Decimal(pedido.get('precio_orden') or '0')
                        saldo_pendiente = precio_orden - total_pagado
                        pedido['saldo_pendiente'] = str(saldo_pendiente)

                        pedidos_enriquecidos.append(pedido)

            # 3. Combinar los datos
            perfil_completo = cliente_data
            perfil_completo['pedidos'] = pedidos_enriquecidos
            
            return self.success_response(data=perfil_completo)

        except Exception as e:
            logger.error(f"Error obteniendo el perfil del cliente {cliente_id}: {str(e)}")
            return self.error_response('Error interno del servidor.', 500)
    
    def recalcular_estado_crediticio_todos_los_clientes(self) -> int:
        """
        Recalcula el estado crediticio para todos los clientes.
        Devuelve el número de clientes cuyo estado fue modificado.
        """
        try:
            clientes_afectados = 0
            clientes_result = self.model.get_all()
            if not clientes_result.get('success'):
                logger.error("No se pudieron obtener los clientes para recalcular el estado crediticio.")
                return 0

            for cliente in clientes_result['data']:
                pedidos_vencidos_result = self.pedido_controller.model.find_all({'id_cliente': cliente['id'], 'estado_pago': 'vencido'})
                
                if pedidos_vencidos_result.get('success'):
                    conteo_vencidos = len(pedidos_vencidos_result['data'])
                    umbral_alertado = Config.CREDIT_ALERT_THRESHOLD
                    
                    nuevo_estado = 'alertado' if conteo_vencidos > umbral_alertado else 'normal'

                    if cliente.get('estado_crediticio') != nuevo_estado:
                        self.model.update(cliente['id'], {'estado_crediticio': nuevo_estado}, 'id')
                        clientes_afectados += 1
            return clientes_afectados
        except Exception as e:
            logger.error(f"Error recalculando el estado crediticio de todos los clientes: {e}", exc_info=True)
            return 0

    def obtener_datos_para_pago(self, pedido_id: int, cliente_id: int) -> tuple:
        """
        Obtiene los datos de un pedido para la página de pago, verificando la propiedad.
        """
        try:
            # 1. Obtener el pedido completo
            pedido_response, status_code = self.pedido_controller.obtener_pedido_por_id(pedido_id)
            if status_code != 200:
                return self.error_response('Pedido no encontrado.', 404)
            
            pedido = pedido_response.get('data', {})

            # 2. Verificar que el pedido pertenece al cliente en sesión
            if pedido.get('id_cliente') != cliente_id:
                return self.error_response('No tienes permiso para pagar este pedido.', 403)

            # 3. Calcular el saldo pendiente
            from app.controllers.pago_controller import PagoController
            pago_controller = PagoController()
            pagos_res, _ = pago_controller.get_pagos_by_pedido_id(pedido_id)
            
            pagos_data = pagos_res.get('data', [])
            total_pagado = sum(Decimal(p['monto']) for p in pagos_data)
            precio_orden = Decimal(pedido.get('precio_orden') or '0')
            saldo_pendiente = precio_orden - total_pagado
            
            pedido['saldo_pendiente'] = str(saldo_pendiente)

            return self.success_response(data=pedido)

        except Exception as e:
            logger.error(f"Error obteniendo datos para la página de pago del pedido {pedido_id}: {str(e)}")
            return self.error_response('Error interno del servidor.', 500)
