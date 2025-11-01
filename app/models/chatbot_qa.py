from app.models.base_model import BaseModel

class ChatbotQA(BaseModel):
    """
    Modelo para gestionar las preguntas y respuestas del chatbot en la base de datos.
    """

    def get_table_name(self) -> str:
        """
        Devuelve el nombre de la tabla de la base de datos.
        """
        return "chatbot_qa"

    def create_table_if_not_exists(self):
        """
        Crea la tabla 'chatbot_qa' en la base de datos si no existe.
        Esta función está pensada para ser ejecutada una sola vez durante la configuración.
        """
        query = """
        CREATE TABLE IF NOT EXISTS chatbot_qa (
            id SERIAL PRIMARY KEY,
            pregunta TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            activo BOOLEAN DEFAULT TRUE,
            creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            # Usamos una conexión directa para ejecutar SQL que no es de Supabase
            with self.db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
            return {'success': True, 'message': 'Tabla chatbot_qa verificada/creada.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

