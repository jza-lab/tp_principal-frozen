from marshmallow import Schema, fields, validate, post_load
from datetime import date
from app.models.pedido import Pedido, PedidoItem

class PedidoItemSchema(Schema):
    """
    Schema para validar cada ítem dentro de un pedido.
    """
    id = fields.Int(dump_only=True)
    producto_id = fields.Int(required=True)
    cantidad = fields.Float(required=True, validate=validate.Range(min=0.01))

    # Campos gestionados por el sistema, no por el usuario en la creación.
    estado = fields.Str(dump_only=True)
    orden_produccion_id = fields.Int(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @post_load
    def make_item(self, data, **kwargs):
        # Devuelve una instancia de PedidoItem para que pueda ser anidada
        return PedidoItem(**data)

class PedidoSchema(Schema):
    """
    Schema para la validación de datos de pedidos de clientes,
    adaptado para soportar múltiples ítems.
    """
    id = fields.Int(dump_only=True)
    nombre_cliente = fields.Str(required=True, validate=validate.Length(min=1))
    fecha_solicitud = fields.Date(required=True)

    # Campo anidado para los ítems del pedido
    items = fields.List(
        fields.Nested(PedidoItemSchema),
        required=True,
        validate=validate.Length(min=1, error="El pedido debe contener al menos un ítem.")
    )

    estado = fields.Str(dump_only=True, load_default='PENDIENTE')
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @post_load
    def make_pedido(self, data, **kwargs):
        # Para actualizaciones parciales, devolvemos el diccionario.
        if kwargs.get('partial'):
            return data

        # Asegura que la fecha sea un objeto date.
        if isinstance(data.get('fecha_solicitud'), str):
            data['fecha_solicitud'] = date.fromisoformat(data['fecha_solicitud'])

        # Crea la instancia completa del dataclass Pedido con sus ítems.
        return Pedido(**data)