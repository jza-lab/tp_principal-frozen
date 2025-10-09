from marshmallow import Schema, fields

class DireccionSchema(Schema):
    """
    Schema para la validación de datos de direcciones de usuario.
    """
    id = fields.Int(dump_only=True)
    calle = fields.Str(required=True)
    altura = fields.Int(required=True)
    piso = fields.Str(allow_none=True)
    depto = fields.Str(allow_none=True)
    codigo_postal = fields.Str(allow_none=True)
    localidad = fields.Str(required=True)
    provincia = fields.Str(required=True)
    latitud = fields.Float(dump_only=True, allow_none=True)
    longitud = fields.Float(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)