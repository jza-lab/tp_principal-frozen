from marshmallow import Schema, fields, validate
from app.schemas.reclamo_mensaje_schema import ReclamoMensajeSchema # Importar el nuevo schema

class ReclamoSchema(Schema):
    """
    Esquema de Marshmallow para la validación de datos de reclamos.
    """
    id = fields.Int(dump_only=True)
    pedido_id = fields.Int(required=True, error_messages={"required": "El ID del pedido es obligatorio."})
    cliente_id = fields.Int(required=True, error_messages={"required": "El ID del cliente es obligatorio."})

    categoria = fields.Str(
        required=True,
        validate=validate.OneOf(
            ["no_llego", "mal_estado", "envio_incorrecto","pedido_incompleto", "otro"],
            error="Categoría no válida."
        ),
        error_messages={"required": "La categoría del reclamo es obligatoria."}
    )

    fecha_recepcion = fields.Date(
        required=True,
        error_messages={"required": "La fecha de recepción es obligatoria."}
    )

    comentarios = fields.Str(required=False, allow_none=True)

    # Campo de solo lectura para la fecha de creación
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    estado = fields.Str(
        validate=validate.OneOf(["pendiente", "respondida", "solucionada", "cancelado"]), # Añadidos nuevos estados
        load_default="pendiente",  # Valor por defecto al cargar datos
        dump_default="pendiente"  # Valor por defecto al serializar
    )

    # Campos anidados (solo para serialización)
    mensajes = fields.List(fields.Nested(ReclamoMensajeSchema()), dump_only=True)
    cliente = fields.Nested('ClienteSchema', dump_only=True, only=('nombre',))
    pedido = fields.Nested('PedidoSchema', dump_only=True, only=('id',))