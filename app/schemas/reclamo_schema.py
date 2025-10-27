from marshmallow import Schema, fields, validate

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

    estado = fields.Str(
        validate=validate.OneOf(["pendiente", "resuelto"]),
        missing="pendiente",  # Valor por defecto al cargar datos
        dump_default="pendiente"  # Valor por defecto al serializar
    )
