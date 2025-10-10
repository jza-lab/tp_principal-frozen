from marshmallow import Schema, fields

class ReservaProductoSchema(Schema):
    id = fields.Int(dump_only=True)
    lote_producto_id = fields.Int(required=True)
    pedido_id = fields.Int(required=True)
    pedido_item_id = fields.Int(required=True)
    cantidad_reservada = fields.Decimal(required=True, as_string=True)
    estado = fields.Str(dump_default='RESERVADO')
    usuario_reserva_id = fields.Int(required=True, allow_none=True)