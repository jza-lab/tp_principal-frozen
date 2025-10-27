from marshmallow import Schema, fields

class ReclamoMensajeSchema(Schema):
    """
    Esquema de Marshmallow para la validación de mensajes de reclamos.
    """
    id = fields.Int(dump_only=True)
    reclamo_id = fields.Int(required=True)
    usuario_id = fields.Int(allow_none=True) # ID del admin que responde
    cliente_id = fields.Int(allow_none=True) # ID del cliente que responde
    mensaje = fields.Str(required=True)
    created_at = fields.DateTime(dump_only=True)

    # Campos de solo lectura para datos anidados
    autor_admin = fields.Nested('UsuarioSchema', dump_only=True, only=('nombre', 'apellido'))
    autor_cliente = fields.Nested('ClienteSchema', dump_only=True, only=('nombre',))