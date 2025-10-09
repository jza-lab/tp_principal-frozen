from marshmallow import Schema, fields, validate

ITEM_ESTADOS_VALIDOS = [
    'PENDIENTE',      # Recién agregado al pedido
    'EN_PRODUCCION',  # El producto está siendo fabricado/preparado
    'ALISTADO',       # Listo para ser empacado
    'CANCELADO_ITEM'  # El ítem específico fue cancelado
]

class PedidoItemSchema(Schema):
    """
    Schema para la validación de un item dentro de un pedido.
    """
    id = fields.Int(required=False, allow_none=True)
    producto_id = fields.Int(required=True, error_messages={"required": "El ID del producto es obligatorio."})
    cantidad = fields.Int(
        required=True, 
        validate=validate.Range(min=1, error="La cantidad debe ser un número entero mayor que cero."),
        error_messages={"invalid": "La cantidad debe ser un número entero válido."}
    )
    orden_produccion_id = fields.Int(allow_none=True)
    
    estado = fields.Str(
        validate=validate.OneOf(ITEM_ESTADOS_VALIDOS),
        dump_only=True
    )

    producto_nombre = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class PedidoSchema(Schema):
    """
    Schema para la validación y serialización de un pedido completo,
    incluyendo sus items.
    """
    nombre_cliente = fields.Str(required=True, validate=validate.Length(min=1, error="El nombre del cliente no puede estar vacío."))
    fecha_solicitud = fields.Date(required=True, error_messages={"required": "La fecha de solicitud es obligatoria."})
    fecha_requerido = fields.Date(allow_none=True)
    precio_orden = fields.Decimal(as_string=True, allow_none=True)

    estado = fields.Str(validate=validate.OneOf(['PENDIENTE', 'EN_PROCESO', 'LISTO_PARA_ENTREGA', 'COMPLETADO', 'CANCELADO']))

    items = fields.List(
        fields.Nested(PedidoItemSchema),
        required=True,
        validate=validate.Length(min=1, error="El pedido debe contener al menos un producto.")
    )

    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)