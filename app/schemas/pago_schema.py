from marshmallow import Schema, fields, validate

class PagoSchema(Schema):
    id_pedido = fields.Int(required=True)
    monto = fields.Decimal(required=True, places=2, validate=validate.Range(min=0.01))
    metodo_pago = fields.Str(required=True, validate=validate.OneOf(["transferencia", "tarjeta_credito", "tarjeta_debito", "efectivo"]))
    datos_adicionales = fields.Dict(required=False, allow_none=True)
    id_usuario_registro = fields.Int(required=True)
    
    class Meta:
        strict = True
