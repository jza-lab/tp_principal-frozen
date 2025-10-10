from marshmallow import Schema, fields, validate

class ReservaInsumoSchema(Schema):
    """
    Schema para validar y serializar los datos de las reservas de insumos.
    """
    id = fields.Int(dump_only=True)
    orden_produccion_id = fields.Int(required=True)
    lote_inventario_id = fields.Int(required=True)
    insumo_id = fields.Int(required=True)

    cantidad_reservada = fields.Decimal(
        required=True,
        as_string=True, # Importante para la serialización
        validate=validate.Range(min=0.001, error="La cantidad debe ser mayor que cero.")
    )

    estado = fields.Str(
        dump_default='RESERVADO',
        validate=validate.OneOf(['RESERVADO', 'CONSUMIDO', 'CANCELADO'])
    )

    created_at = fields.DateTime(dump_only=True)
    usuario_reserva_id = fields.Int(required=True, allow_none=True)