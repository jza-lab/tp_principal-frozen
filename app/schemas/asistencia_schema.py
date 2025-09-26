from marshmallow import Schema, fields, validate

class AsistenciaSchema(Schema):
    """
    Schema para la validación de los datos de un registro de asistencia.
    """
    id = fields.Int(dump_only=True)
    usuario_id = fields.Int(required=True)

    tipo = fields.Str(
        required=True,
        validate=validate.OneOf(['ENTRADA', 'SALIDA'], error="El tipo debe ser 'ENTRADA' o 'SALIDA'.")
    )

    fecha_hora = fields.DateTime(dump_only=True) # Gestionado por la BD
    observaciones = fields.Str(allow_none=True)