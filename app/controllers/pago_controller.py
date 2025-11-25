from .base_controller import BaseController
from app.models.pago import PagoModel
from app.models.pedido import PedidoModel
from app.schemas.pago_schema import PagoSchema
from werkzeug.utils import secure_filename
from decimal import Decimal, InvalidOperation

class PagoController(BaseController):
    def __init__(self):
        super().__init__()
        self.pago_model = PagoModel()
        self.pedido_model = PedidoModel()
        from app.controllers.storage_controller import StorageController
        self.storage_controller = StorageController()
        self.pago_schema = PagoSchema()

    def registrar_pago(self, pago_data, file=None):
        try:
            # 1. Transformar y validar datos del formulario
            # El schema espera un dict para 'datos_adicionales', pero el form envía un string.
            # Lo convertimos a un dict simple antes de validar.
            if 'datos_adicionales' in pago_data and isinstance(pago_data['datos_adicionales'], str):
                texto_adicional = pago_data['datos_adicionales'].strip()
                if texto_adicional:
                    pago_data['datos_adicionales'] = {'nota': texto_adicional}
                else:
                    pago_data['datos_adicionales'] = None # Si está vacío, lo tratamos como nulo

            errors = self.pago_schema.validate(pago_data)
            if errors:
                return self.error_response(errors, 400)

            id_pedido = pago_data['id_pedido']
            monto_pagado = Decimal(pago_data['monto'])

            # 2. Obtener el pedido y calcular el saldo pendiente
            pedido_res = self.pedido_model.find_by_id(id_pedido)
            if not pedido_res.get('success') or not pedido_res.get('data'):
                return self.error_response("El pedido asociado no fue encontrado.", 404)
            
            pedido = pedido_res['data']
            monto_total_pedido = Decimal(pedido.get('precio_orden', 0))

            pagos_existentes_res = self.pago_model.get_pagos_by_pedido_id(id_pedido)
            total_ya_pagado = Decimal(0)
            if pagos_existentes_res.get('success') and pagos_existentes_res.get('data'):
                for pago in pagos_existentes_res['data']:
                    total_ya_pagado += Decimal(pago['monto'])

            saldo_pendiente = monto_total_pedido - total_ya_pagado

            # 3. Validar que el monto no exceda el saldo (se mantiene por seguridad)
            if monto_pagado > saldo_pendiente + Decimal('0.01'):
                error_msg = f"El monto a pagar (${monto_pagado:.2f}) no puede exceder el saldo pendiente (${saldo_pendiente:.2f})."
                return self.error_response(error_msg, 400)

            # 4. Subir archivo si existe (movido antes para tener la URL lista)
            comprobante_url = None
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = f"comprobantes_pago/{id_pedido}/{filename}"

                upload_response, status_code = self.storage_controller.upload_file(
                    file=file, bucket_name='comprobantes_de_pago', destination_path=file_path
                )

                if not upload_response.get('success'):
                    return self.error_response(upload_response.get('error', 'Error al subir el archivo'), status_code)

                comprobante_url = upload_response.get('url')

            # 5. Preparar y registrar el pago usando el modelo
            pago_to_create = {
                'id_pedido': id_pedido,
                'monto': str(monto_pagado),
                'metodo_pago': pago_data['metodo_pago'],
                'datos_adicionales': pago_data.get('datos_adicionales'),
                'comprobante_url': comprobante_url,
                'estado': 'verificado',
                'id_usuario_registro': pago_data['id_usuario_registro']
            }
            
            result = self.pago_model.create(pago_to_create)
            if not result.get('success'):
                 return self.error_response("No se pudo registrar el pago en la base de datos.", 500)

            # 6. Actualizar estado del pedido
            if pedido.get('condicion_venta') == 'contado':
                nuevo_estado_pago = 'Pagado'
            else:
                nuevo_total_pagado = total_ya_pagado + monto_pagado
                nuevo_saldo_pendiente = monto_total_pedido - nuevo_total_pagado
                
                nuevo_estado_pago = 'Pagado Parcialmente'
                if nuevo_saldo_pendiente <= 0:
                    nuevo_estado_pago = 'Pagado'

            update_data = {'estado_pago': nuevo_estado_pago}
            update_result = self.pedido_model.update(id_pedido, update_data)

            if not update_result.get('success'):
                # Log de advertencia si la actualización falla pero el pago se creó
                print(f"ADVERTENCIA: Pago {result['data']['id_pago']} registrado, pero no se pudo actualizar el estado del pedido {id_pedido} a '{nuevo_estado_pago}'.")


            return self.success_response(result['data'], message="Pago registrado con éxito.", status_code=201)

        except InvalidOperation:
            return self.error_response("El monto proporcionado no es un número válido.", 400)
        except Exception as e:
            print(f"Error en PagoController.registrar_pago: {e}")
            return self.error_response("Ocurrió un error inesperado al procesar el pago.", 500)
            
    def get_pagos_by_pedido_id(self, id_pedido):
        pagos_res = self.pago_model.get_pagos_by_pedido_id(id_pedido)
        if not pagos_res.get('success'):
            return self.error_response("Error al obtener los pagos del pedido.", 500)
        return self.success_response(pagos_res.get('data', []))

    def get_pago_by_id(self, id_pago):
        result = self.pago_model.find_by_id(id_pago)
        if not result.get('success'):
             return self.error_response("Pago no encontrado.", 404)
        return self.success_response(result.get('data'))
