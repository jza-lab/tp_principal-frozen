from flask import jsonify
from app.models.chatbot_qa import ChatbotQA

class ChatbotController:
    
    def __init__(self):
        self.model = ChatbotQA()
    
    def get_all_active_qas(self):
        """Obtiene todas las Q&As activas de nivel superior y añade una opción de fallback."""
        try:
            # Filtrar por parent_id IS NULL para obtener solo las preguntas principales
            result = self.model.db.table('chatbot_qa').select('*').eq('activo', True).is_('parent_id', None).execute()
            
            # Añadir la opción estática al final
            qas = result.data
            qas.append({
                'id': -1,
                'pregunta': 'No encuentro mi respuesta',
                'respuesta': 'Serás redirigido a la página de consultas.',
                'type': 'redirect',
                'url': '/public/consulta'
            })
            
            return jsonify({
                'success': True,
                'data': qas
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    def get_children_qas(self, parent_id):
        """Obtiene las Q&As hijas de una pregunta padre."""
        try:
            result = self.model.db.table('chatbot_qa').select('*').eq('activo', True).eq('parent_id', parent_id).execute()
            
            return jsonify({
                'success': True,
                'data': result.data
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    def get_all_qas_for_admin(self):
        """Obtiene todas las Q&As (activas e inactivas) para el admin"""
        try:
            result = self.model.db.table('chatbot_qa').select('*').order('creado_en', desc=True).execute()
            
            return jsonify({
                'success': True,
                'data': result.data
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    def create_qa(self, data):
        """Crea una nueva Q&A"""
        try:
            pregunta = data.get('pregunta')
            respuesta = data.get('respuesta')
            activo_value = data.get('activo', 'on')
            parent_id = data.get('parent_id')

            if not pregunta or not respuesta:
                return jsonify({
                    'success': False,
                    'error': 'Pregunta y respuesta son requeridas'
                }), 400
            
            nuevo_registro = {
                'pregunta': pregunta.strip(),
                'respuesta': respuesta.strip(),
                'activo': (activo_value == 'on'),
                'parent_id': int(parent_id) if parent_id and parent_id.isdigit() else None
            }
            
            result = self.model.db.table('chatbot_qa').insert(nuevo_registro).execute()
            
            return jsonify({
                'success': True,
                'message': 'Q&A creada exitosamente',
                'data': result.data[0] if result.data else {}
            }), 201
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    def update_qa(self, qa_id, data):
        """Actualiza una Q&A (pregunta, respuesta y parent_id)"""
        try:
            pregunta = data.get('pregunta')
            respuesta = data.get('respuesta')
            parent_id = data.get('parent_id')

            if not pregunta or not respuesta:
                return jsonify({
                    'success': False,
                    'error': 'Pregunta y respuesta son requeridas'
                }), 400
            
            actualizacion = {
                'pregunta': pregunta.strip(),
                'respuesta': respuesta.strip(),
                'parent_id': int(parent_id) if parent_id and parent_id.isdigit() else None
            }
            
            result = self.model.db.table('chatbot_qa').update(actualizacion).eq('id', qa_id).execute()
            
            if not result.data:
                return jsonify({
                    'success': False,
                    'error': 'Q&A no encontrada'
                }), 404
            
            return jsonify({
                'success': True,
                'message': 'Q&A actualizada exitosamente',
                'data': result.data[0]
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    def toggle_qa_active(self, qa_id, data):
        """Cambia el estado activo/inactivo de una Q&A"""
        try:
            activo_value = data.get('activo', 'off')
            nuevo_estado = (activo_value == 'on')
            
            result = self.model.db.table('chatbot_qa').update({
                'activo': nuevo_estado
            }).eq('id', qa_id).execute()
            
            if not result.data:
                return jsonify({
                    'success': False,
                    'error': 'Q&A no encontrada'
                }), 404
            
            return jsonify({
                'success': True,
                'message': f'Q&A {"activada" if nuevo_estado else "desactivada"} exitosamente',
                'data': result.data[0]
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    def delete_qa(self, qa_id):
        """Deshabilita una Q&A"""
        try:
            result = self.model.db.table('chatbot_qa').update({
                'activo': False
            }).eq('id', qa_id).execute()
            
            if not result.data:
                return jsonify({
                    'success': False,
                    'error': 'Q&A no encontrada'
                }), 404
            
            return jsonify({
                'success': True,
                'message': 'Q&A deshabilitada exitosamente'
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500