# tp_principal-frozen/app/schemas/configuracion_schema.py
from marshmallow import Schema, fields

class ConfiguracionSchema(Schema):
    """
    Esquema para la tabla de configuracion (clave-valor).
    """
    clave = fields.Str(required=True)
    valor = fields.Str(required=True)
    
    # Campos opcionales de auditoría que Marshmallow debe ignorar al cargar
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)