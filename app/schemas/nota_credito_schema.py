from marshmallow import Schema, fields

class NotaCreditoSchema(Schema):
    """
    Esquema de Marshmallow para la validación de datos de Notas de Crédito.
    """
    id = fields.Int(dump_only=True)
    codigo_nc = fields.Str(required=True)
    cliente_id = fields.Int(required=True)
    pedido_origen_id = fields.Int(allow_none=True)
    alerta_origen_id = fields.Int(allow_none=True)
    monto = fields.Decimal(as_string=True, required=True)
    motivo = fields.Str(allow_none=True)
    fecha_emision = fields.DateTime(dump_only=True)
    estado = fields.Str(dump_default="Emitida")

    # Campos anidados para enriquecer la respuesta
    cliente = fields.Nested('ClienteSchema', dump_only=True, only=('nombre',))
    pedido = fields.Nested('PedidoSchema', dump_only=True, only=('id',))
