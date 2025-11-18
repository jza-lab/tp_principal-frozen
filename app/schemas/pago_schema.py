from marshmallow import Schema, fields, validate

class PagoSchema(Schema):
    id_pago = fields.Int(dump_only=True)
    id_pedido = fields.Int(required=True)
    fecha = fields.DateTime(dump_only=True)
    monto = fields.Decimal(required=True, as_string=True, validate=validate.Range(min=0))
    metodo_pago = fields.Str(required=True, validate=validate.OneOf(['transferencia', 'tarjeta', 'efectivo']))
    datos_adicionales = fields.Str(allow_none=True)
    comprobante_url = fields.Str(allow_none=True)
    estado = fields.Str(validate=validate.OneOf(['pendiente', 'verificado', 'rechazado']), dump_default='pendiente')
    id_usuario_registro = fields.Int(required=True)

    class Meta:
        strict = True
