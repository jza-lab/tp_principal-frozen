from marshmallow import Schema, fields, validate
from app.models.pedido import Pedido, PedidoItem
from datetime import date


# Definimos las opciones de estado permitidas para un ítem del pedido
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
    # FIX PRINCIPAL:
    # El campo 'id' debe ser cargable (no dump_only) para que Marshmallow 
    # no lo marque como "Unknown field" al recibirlo del formulario.
    # Es opcional (required=False) porque los ítems nuevos no tendrán ID.
    id = fields.Int(required=False, allow_none=True)
    
    # Campos para la carga (creación/actualización)
    producto_id = fields.Int(required=True, error_messages={"required": "El ID del producto es obligatorio."})
    cantidad = fields.Float(required=True, validate=validate.Range(min=0.01, error="La cantidad debe ser mayor que cero."))
    
    # Habilitamos el estado para que pueda ser cargado/editado por el usuario.
    # FIX APLICADO: Se elimina 'load_default' para evitar que Marshmallow
    # fuerce 'PENDIENTE' durante las actualizaciones.
    estado = fields.Str(
        validate=validate.OneOf(ITEM_ESTADOS_VALIDOS),
        required=True # Hacemos requerido para asegurar que se envía un estado válido, aunque el HTML lo garantiza.
    )

    # Campos de solo lectura (para mostrar datos)
    producto_nombre = fields.Str(dump_only=True)


class PedidoItemSchema(Schema):
    """
    Schema para la validación y serialización de un pedido completo,
    incluyendo sus items.
    """
    # Campos para la carga (creación/actualización)
    nombre_cliente = fields.Str(required=True, validate=validate.Length(min=1, error="El nombre del cliente no puede estar vacío."))
    fecha_solicitud = fields.Date(required=True, error_messages={"required": "La fecha de solicitud es obligatoria."})
    
    # Para la actualización, el estado del pedido principal puede ser enviado.
    # Para la creación, se establecerá un valor predeterminado en el controlador si no se proporciona.
    estado = fields.Str(validate=validate.OneOf(['PENDIENTE', 'EN_PROCESO', 'LISTO_PARA_ENTREGA', 'COMPLETADO', 'CANCELADO']))

    # Lista anidada de items. Debe contener al menos un item al crear.
    items = fields.List(
        fields.Nested(PedidoItemSchema),
        required=True,
        validate=validate.Length(min=1, error="El pedido debe contener al menos un producto.")
    )

    # Campos de solo lectura (generados por el sistema)
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
