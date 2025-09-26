from marshmallow import Schema, fields

class ResponseSchema(Schema):
    """Esquema para respuestas estandarizadas"""
    success = fields.Bool(required=True)
    data = fields.Raw(allow_none=True)
    message = fields.Str(allow_none=True)
    error = fields.Str(allow_none=True)
    details = fields.Dict(allow_none=True)