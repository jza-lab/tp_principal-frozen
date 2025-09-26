from marshmallow import Schema, fields, validate, post_load
from datetime import date

class PedidoSchema(Schema):
    """
    Schema para la validación de datos de pedidos de clientes.
    """
    id = fields.Int(dump_only=True)
    producto_id = fields.Int(required=True)
    cantidad = fields.Float(required=True, validate=validate.Range(min=0.01))
    nombre_cliente = fields.Str(required=True, validate=validate.Length(min=1))
    fecha_solicitud = fields.Date(required=True)

    # El estado no es enviado por el cliente, se gestiona internamente.
    estado = fields.Str(dump_only=True, load_default='PENDIENTE')

    # Campo para la trazabilidad con la orden de producción
    orden_produccion_id = fields.Int(dump_only=True, allow_none=True)

    creado_en = fields.DateTime(dump_only=True)
    actualizado_en = fields.DateTime(dump_only=True)

    @post_load
    def make_pedido(self, data, **kwargs):
        # Asegura que la fecha sea un objeto date y no un string
        if isinstance(data.get('fecha_solicitud'), str):
            data['fecha_solicitud'] = date.fromisoformat(data['fecha_solicitud'])
        return data