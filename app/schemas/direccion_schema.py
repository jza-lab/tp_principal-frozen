from marshmallow import Schema, fields, validates_schema, ValidationError
from marshmallow.validate import Length, Regexp

class DireccionSchema(Schema):
    """
    Schema para la validación de datos de direcciones de usuario.
    """
    id = fields.Int(dump_only=True)
    calle = fields.Str(required=True)
    altura = fields.Int(required=True)
    
    piso = fields.Str(
        allow_none=True,
        validate=[
            Length(max=10, error="El piso no debe exceder los 10 caracteres."),
            Regexp(r'^[a-zA-Z0-9\s]*$', error="El piso solo puede contener letras y números.")
        ]
    )
    
    depto = fields.Str(
        allow_none=True,
        validate=[
            Length(max=10, error="El depto no debe exceder los 10 caracteres."),
            Regexp(r'^[a-zA-Z0-9\s]*$', error="El depto solo puede contener letras y números.")
        ]
    )
    
    codigo_postal = fields.Str(
        allow_none=True,
        validate=Regexp(
            r'(^\d{4}$)|(^[A-Z]\d{4}[A-Z]{3}$)',
            error="El código postal debe tener 4 dígitos o el formato CPA (ej: C1234ABC)."
        )
    )
    
    localidad = fields.Str(required=True)
    provincia = fields.Str(required=True)
    latitud = fields.Float(dump_only=True, allow_none=True)
    longitud = fields.Float(dump_only=True, allow_none=True)
    created_at = fields.Str(dump_only=True)

    @validates_schema
    def validate_piso_depto_consistency(self, data, **kwargs):
        """
        Si se proporciona un departamento, el piso también debe ser proporcionado.
        """
        if data.get('depto') and not data.get('piso'):
            raise ValidationError(
                "Debe proporcionar un piso si ingresa un departamento.",
                "piso"  # Campo al que se asocia el error
            )