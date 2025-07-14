"""
Rutas API del agente
Endpoints para comunicación con el frontend
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from datetime import datetime
import time
import uuid
import os
import json
import zipfile
import tempfile
import asyncio
from pathlib import Path
from werkzeug.utils import secure_filename
from src.utils.json_encoder import MongoJSONEncoder, mongo_json_serializer
from src.tools.environment_setup_manager import EnvironmentSetupManager

agent_bp = Blueprint('agent', __name__)

# Almacenamiento temporal para compartir conversaciones
shared_conversations = {}

# Almacenamiento temporal para archivos por tarea
task_files = {}

@agent_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint de salud del agente"""
    try:
        # Obtener servicios
        ollama_service = current_app.ollama_service
        tool_manager = current_app.tool_manager
        database_service = current_app.database_service
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'ollama': ollama_service.is_healthy(),
                'tools': len(tool_manager.get_available_tools()),
                'database': database_service.is_connected()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/deep-research/progress/<task_id>', methods=['GET'])
def get_deep_research_progress(task_id):
    """Endpoint para obtener progreso de DeepResearch en tiempo real"""
    try:
        # Obtener tool manager
        tool_manager = current_app.tool_manager
        
        # Obtener la herramienta de investigación profunda
        enhanced_tool = tool_manager.tools.get('enhanced_deep_research')
        
        if not enhanced_tool:
            return jsonify({'error': 'Enhanced Deep Research tool not found'}), 404
        
        # Obtener estado del progreso
        progress_status = enhanced_tool.get_progress_status()
        
        # Obtener los pasos predefinidos
        steps = enhanced_tool.get_progress_steps()
        
        return jsonify({
            'task_id': task_id,
            'is_active': progress_status.get('is_active', False),
            'current_progress': progress_status.get('current_progress', 0),
            'current_step': progress_status.get('current_step', -1),
            'latest_update': progress_status.get('latest_update'),
            'steps': steps
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@agent_bp.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal para chat con el agente"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        context = data.get('context', {})
        search_mode = data.get('search_mode', None)
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Obtener servicios
        ollama_service = current_app.ollama_service
        tool_manager = current_app.tool_manager
        database_service = current_app.database_service
        
        # Obtener task_id del contexto
        task_id = context.get('task_id')
        
        # Detectar modo de búsqueda desde el mensaje
        original_message = message
        if message.startswith('[WebSearch]'):
            search_mode = 'websearch'
            message = message.replace('[WebSearch]', '').strip()
        elif message.startswith('[DeepResearch]'):
            search_mode = 'deepsearch'
            message = message.replace('[DeepResearch]', '').strip()
        
        # Ejecutar herramientas directamente según el modo de búsqueda
        tool_results = []
        created_files = []
        
        if search_mode == 'websearch':
            # Usar web_search para WebSearch
            try:
                result = tool_manager.execute_tool('web_search', {
                    'query': message,
                    'max_results': 10
                })
                tool_results.append({
                    'tool': 'web_search',
                    'parameters': {'query': message, 'max_results': 10},
                    'result': result
                })
            except Exception as e:
                tool_results.append({
                    'tool': 'web_search',
                    'parameters': {'query': message},
                    'result': {'error': str(e)}
                })
        
        elif search_mode == 'deepsearch':
            # Usar deep_research para DeepResearch
            try:
                result = tool_manager.execute_tool('deep_research', {
                    'query': message,
                    'max_sources': 20,
                    'research_depth': 'comprehensive'
                })
                tool_results.append({
                    'tool': 'deep_research',
                    'parameters': {'query': message, 'max_sources': 20, 'research_depth': 'comprehensive'},
                    'result': result
                })
                
                # Si hay un archivo de informe, agregarlo a los archivos de la tarea
                if result.get('success') and result.get('report_file'):
                    report_file_path = result['report_file']
                    file_info = {
                        'id': str(uuid.uuid4()),
                        'file_id': str(uuid.uuid4()),
                        'task_id': task_id,
                        'name': f'informe_{message.replace(" ", "_")[:30]}.md',
                        'path': report_file_path,
                        'size': os.path.getsize(report_file_path) if os.path.exists(report_file_path) else 0,
                        'type': 'file',
                        'mime_type': 'text/markdown',
                        'source': 'agent',
                        'created_at': datetime.now().isoformat()
                    }
                    
                    # Agregar archivo a la tarea
                    if task_id not in task_files:
                        task_files[task_id] = []
                    task_files[task_id].append(file_info)
                    created_files.append(file_info)
                    
            except Exception as e:
                tool_results.append({
                    'tool': 'deep_research',
                    'parameters': {'query': message, 'max_sources': 20, 'research_depth': 'comprehensive'},
                    'result': {'error': str(e)}
                })
        
        # Generar respuesta con Ollama si no hay modo de búsqueda específico
        if not search_mode:
            response = ollama_service.generate_response(message, context, use_tools=True)
            
            # Ejecutar herramientas adicionales si Ollama las solicita
            if response.get('tool_calls'):
                for tool_call in response['tool_calls']:
                    tool_name = tool_call.get('tool')
                    parameters = tool_call.get('parameters', {})
                    
                    try:
                        result = tool_manager.execute_tool(tool_name, parameters)
                        tool_results.append({
                            'tool': tool_name,
                            'parameters': parameters,
                            'result': result
                        })
                        
                        # Rastrear archivos creados
                        if (tool_name == 'file_manager' and 
                            parameters.get('action') in ['create', 'write'] and
                            result.get('success')):
                            
                            file_path = result.get('path')
                            if file_path:
                                file_info = {
                                    'file_id': str(uuid.uuid4()),
                                    'task_id': task_id,
                                    'name': os.path.basename(file_path),
                                    'path': file_path,
                                    'size': result.get('size', 0),
                                    'type': 'file',
                                    'mime_type': 'text/plain',
                                    'source': 'agent'
                                }
                                
                                # Guardar en la base de datos
                                if database_service.is_connected():
                                    database_service.save_file(file_info)
                                
                                # Mantener compatibilidad con sistema actual
                                if task_id:
                                    if task_id not in task_files:
                                        task_files[task_id] = []
                                    task_files[task_id].append(file_info)
                                    created_files.append(file_info)
                        
                    except Exception as e:
                        tool_results.append({
                            'tool': tool_name,
                            'parameters': parameters,
                            'result': {'error': str(e)}
                        })
        else:
            # Crear respuesta estructurada basada en los resultados de búsqueda
            if tool_results and tool_results[0]['result'].get('success'):
                tool_result = tool_results[0]['result']
                
                if search_mode == 'websearch':
                    # Datos estructurados para WebSearch
                    search_results = tool_result.get('search_results', [])
                    summary = tool_result.get('summary', '')
                    
                    # Formatear fuentes para el componente SearchResults
                    formatted_sources = []
                    for i, result in enumerate(search_results[:5]):
                        formatted_sources.append({
                            'title': result.get('title', f'Resultado {i+1}'),
                            'content': result.get('snippet', 'Sin descripción'),
                            'url': result.get('url', ''),
                            'domain': result.get('domain', ''),
                            'score': result.get('score', 0)
                        })
                    
                    response = {
                        'response': f"🌐 **Búsqueda Web**\n\n**Pregunta:** {message}\n\n**Resumen:**\n{summary}\n\n**Resultados encontrados:** {len(search_results)}\n\n**Fuentes principales:**\n" + 
                                  "\n".join([f"{i+1}. **{result.get('title', 'Sin título')}**\n   {result.get('snippet', 'Sin descripción')[:150]}...\n   🔗 {result.get('url', '')}" 
                                            for i, result in enumerate(search_results[:3])]),
                        'model': 'web-search',
                        'search_data': {
                            'query': message,
                            'directAnswer': summary,
                            'sources': formatted_sources,
                            'images': [],
                            'summary': summary,
                            'search_stats': {'total_sources': len(search_results)},
                            'type': 'websearch'
                        }
                    }
                
                elif search_mode == 'deepsearch':
                    # Datos estructurados para DeepResearch
                    analysis = tool_result.get('analysis', '')
                    key_findings = tool_result.get('key_findings', [])
                    recommendations = tool_result.get('recommendations', [])
                    sources = tool_result.get('sources', [])
                    
                    # Formatear fuentes para el componente SearchResults
                    formatted_sources = []
                    for i, source in enumerate(sources[:5]):
                        formatted_sources.append({
                            'title': f'Fuente {i+1}',
                            'content': source if isinstance(source, str) else str(source),
                            'url': ''
                        })
                    
                    response = {
                        'response': f"🔬 **Investigación Profunda**\n\n**Tema:** {message}\n\n**Análisis Comprehensivo:**\n{analysis}\n\n**Hallazgos Clave:**\n" + 
                                  "\n".join([f"• {finding}" for finding in key_findings[:3]]) + 
                                  "\n\n**Recomendaciones:**\n" + 
                                  "\n".join([f"• {rec}" for rec in recommendations[:3]]),
                        'model': 'deep-research',
                        'search_data': {
                            'query': message,
                            'directAnswer': analysis,
                            'sources': formatted_sources,
                            'type': 'deepsearch',
                            'key_findings': key_findings,
                            'recommendations': recommendations
                        }
                    }
            else:
                # Error en la búsqueda
                error_msg = tool_results[0]['result'].get('error', 'Error desconocido') if tool_results else 'No se pudo realizar la búsqueda'
                response = {
                    'response': f"❌ Error en la búsqueda: {error_msg}",
                    'model': f'{search_mode}-error'
                }
        
        # Guardar la conversación en la base de datos
        if task_id and database_service.is_connected():
            message_data = {
                'message_id': str(uuid.uuid4()),
                'task_id': task_id,
                'content': message,
                'sender': 'user',
                'tool_results': tool_results,
                'search_mode': search_mode
            }
            database_service.add_message_to_conversation(task_id, message_data)
            
            # Guardar también la respuesta del agente
            response_data = {
                'message_id': str(uuid.uuid4()),
                'task_id': task_id,
                'content': response.get('response', ''),
                'sender': 'agent',
                'tool_results': tool_results,
                'search_mode': search_mode
            }
            database_service.add_message_to_conversation(task_id, response_data)
        
        return jsonify({
            'response': response.get('response', 'Sin respuesta'),
            'tool_calls': response.get('tool_calls', []),
            'tool_results': tool_results,
            'created_files': created_files,
            'search_mode': search_mode,
            'search_data': response.get('search_data'),  # Datos estructurados para frontend
            'timestamp': datetime.now().isoformat(),
            'model': response.get('model', 'unknown')
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/status', methods=['GET'])
def status():
    """Obtener estado del agente y servicios"""
    try:
        ollama_service = current_app.ollama_service
        tool_manager = current_app.tool_manager
        
        # Verificar estado de Ollama
        ollama_healthy = ollama_service.is_healthy()
        available_models = ollama_service.get_available_models() if ollama_healthy else []
        current_model = ollama_service.get_current_model()
        
        # Obtener herramientas disponibles
        tools = tool_manager.get_available_tools()
        
        return jsonify({
            'status': 'healthy' if ollama_healthy else 'degraded',
            'ollama_status': 'connected' if ollama_healthy else 'disconnected',
            'available_models': available_models,
            'current_model': current_model,
            'tools_count': len(tools),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/tools', methods=['GET'])
def tools():
    """Obtener lista de herramientas disponibles"""
    try:
        tool_manager = current_app.tool_manager
        available_tools = tool_manager.get_available_tools()
        
        return jsonify({
            'tools': available_tools,
            'count': len(available_tools),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/models', methods=['GET'])
def models():
    """Obtener modelos disponibles en Ollama"""
    try:
        ollama_service = current_app.ollama_service
        available_models = ollama_service.get_available_models()
        current_model = ollama_service.get_current_model()
        
        return jsonify({
            'models': available_models,
            'current_model': current_model,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/models', methods=['POST'])
def set_model():
    """Cambiar modelo activo"""
    try:
        data = request.get_json()
        model_name = data.get('model')
        
        if not model_name:
            return jsonify({'error': 'Model name is required'}), 400
        
        ollama_service = current_app.ollama_service
        success = ollama_service.set_model(model_name)
        
        if success:
            return jsonify({
                'message': f'Model changed to {model_name}',
                'current_model': model_name,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'error': f'Model {model_name} not available',
                'timestamp': datetime.now().isoformat()
            }), 400
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/share', methods=['POST'])
def share_conversation():
    """Crear enlace compartible para una conversación"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        task_title = data.get('task_title', 'Conversación')
        messages = data.get('messages', [])
        
        if not task_id:
            return jsonify({'error': 'task_id is required'}), 400
        
        # Generar ID único para el enlace compartido
        share_id = str(uuid.uuid4())
        
        # Guardar conversación
        shared_conversations[share_id] = {
            'task_id': task_id,
            'task_title': task_title,
            'messages': messages,
            'created_at': datetime.now().isoformat(),
            'share_id': share_id
        }
        
        # Generar enlace (en producción sería tu dominio)
        share_link = f"{request.host_url}shared/{share_id}"
        
        return jsonify({
            'share_id': share_id,
            'share_link': share_link,
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/shared/<share_id>', methods=['GET'])
def get_shared_conversation(share_id):
    """Obtener conversación compartida"""
    try:
        if share_id not in shared_conversations:
            return jsonify({'error': 'Shared conversation not found'}), 404
        
        conversation = shared_conversations[share_id]
        return jsonify({
            'conversation': conversation,
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/files/<task_id>', methods=['GET'])
def get_task_files(task_id):
    """Obtener archivos de una tarea específica"""
    try:
        # Convertir ObjectId a string en los archivos
        files = task_files.get(task_id, [])
        
        # Asegurarse de que todos los archivos tienen un ID
        for file in files:
            if 'id' not in file and 'file_id' in file:
                file['id'] = file['file_id']
            if '_id' in file:
                file['_id'] = str(file['_id'])
        
        return jsonify({
            'files': files,
            'count': len(files),
            'task_id': task_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/download/<file_id>', methods=['GET'])
def download_file(file_id):
    """Descargar un archivo específico"""
    try:
        # Buscar archivo por ID en todos los tasks
        found_file = None
        for task_id, files in task_files.items():
            for file_info in files:
                if file_info['id'] == file_id:
                    found_file = file_info
                    break
            if found_file:
                break
        
        if not found_file:
            return jsonify({'error': 'File not found'}), 404
        
        file_path = found_file['path']
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found on disk'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=found_file['name']
        )
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/download-selected', methods=['POST'])
def download_selected_files():
    """Descargar archivos seleccionados como ZIP"""
    try:
        data = request.get_json()
        file_ids = data.get('file_ids', [])
        
        if not file_ids:
            return jsonify({'error': 'No file IDs provided'}), 400
        
        # Buscar archivos por IDs
        found_files = []
        for task_id, files in task_files.items():
            for file_info in files:
                if file_info['id'] in file_ids:
                    found_files.append(file_info)
        
        if not found_files:
            return jsonify({'error': 'No files found'}), 404
        
        # Crear archivo ZIP temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
            with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_info in found_files:
                    file_path = file_info['path']
                    if os.path.exists(file_path):
                        zip_file.write(file_path, file_info['name'])
            
            zip_path = tmp_zip.name
        
        # Enviar archivo ZIP
        return send_file(
            zip_path,
            as_attachment=True,
            download_name='selected-files.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/download-all/<task_id>', methods=['GET'])
def download_all_files(task_id):
    """Descargar todos los archivos de una tarea como ZIP"""
    try:
        files = task_files.get(task_id, [])
        
        if not files:
            return jsonify({'error': 'No files found for this task'}), 404
        
        # Crear archivo ZIP temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
            with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_info in files:
                    file_path = file_info['path']
                    if os.path.exists(file_path):
                        zip_file.write(file_path, file_info['name'])
            
            zip_path = tmp_zip.name
        
        # Enviar archivo ZIP
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=f'task-{task_id}-files.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/upload-files', methods=['POST'])
def upload_files():
    """Subir archivos para una tarea específica"""
    try:
        task_id = request.form.get('task_id')
        if not task_id:
            return jsonify({'error': 'task_id is required'}), 400
        
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        if not files or len(files) == 0:
            return jsonify({'error': 'No files provided'}), 400
        
        # Obtener servicios
        database_service = current_app.database_service
        
        # Crear directorio para la tarea si no existe
        task_dir = Path(tempfile.gettempdir()) / 'task_files' / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        uploaded_files = []
        
        for file in files:
            if file.filename == '':
                continue
                
            # Asegurar nombre de archivo seguro
            filename = secure_filename(file.filename)
            file_path = task_dir / filename
            
            # Guardar archivo
            file.save(str(file_path))
            
            # Obtener información del archivo
            file_stats = os.stat(file_path)
            
            # Crear información del archivo
            file_id = str(uuid.uuid4())
            file_info = {
                'id': file_id,
                'file_id': file_id,
                'task_id': task_id,
                'name': filename,
                'path': str(file_path),
                'size': file_stats.st_size,
                'type': 'file',
                'mime_type': file.content_type or 'application/octet-stream',
                'source': 'uploaded',
                'created_at': datetime.now().isoformat()
            }
            
            # Guardar en la base de datos - DESACTIVADO TEMPORALMENTE
            # if database_service.is_connected():
            #     try:
            #         # Convertir ObjectId a string antes de devolver la respuesta
            #         mongo_id = database_service.save_file(file_info)
            #         if mongo_id:
            #             file_info['mongo_id'] = str(mongo_id)
            #     except Exception as e:
            #         print(f"Error saving file to database: {e}")
            
            uploaded_files.append(file_info)
        
        # Mantener compatibilidad con sistema actual
        if task_id not in task_files:
            task_files[task_id] = []
        
        # Agregar archivos a la memoria temporal para compatibilidad
        task_files[task_id].extend(uploaded_files)
        
        # Crear respuesta estructurada para el frontend
        response_data = {
            'success': True,
            'message': f'Uploaded {len(uploaded_files)} files',
            'files': uploaded_files,
            'task_id': task_id,
            'timestamp': datetime.now().isoformat(),
            'upload_data': {
                'files': uploaded_files,
                'count': len(uploaded_files),
                'total_size': sum(f['size'] for f in uploaded_files)
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@agent_bp.route('/create-test-files/<task_id>', methods=['POST'])
def create_test_files(task_id):
    """Crear archivos de prueba para testing de la funcionalidad de descarga"""
    try:
        # Crear directorio de archivos de prueba
        test_dir = Path(tempfile.gettempdir()) / 'task_files' / task_id
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear archivos de prueba
        test_files_data = [
            {
                'name': 'reporte.txt',
                'content': '''Reporte de Análisis de Datos
============================

Fecha: 2025-01-15
Autor: Agente IA

Resumen Ejecutivo:
- Se procesaron 1,000 registros
- Se identificaron 3 patrones principales
- Tasa de éxito: 98.5%

Conclusiones:
El análisis muestra tendencias positivas en los datos procesados.
Se recomienda continuar con la estrategia actual.''',
                'mime_type': 'text/plain'
            },
            {
                'name': 'datos.json',
                'content': '''{
  "analisis": {
    "total_registros": 1000,
    "procesados": 985,
    "errores": 15,
    "tasa_exito": 0.985
  },
  "patrones": [
    {"tipo": "temporal", "frecuencia": 45},
    {"tipo": "geografico", "frecuencia": 32},
    {"tipo": "demografico", "frecuencia": 28}
  ],
  "recomendaciones": [
    "Optimizar proceso de validación",
    "Ampliar conjunto de datos",
    "Implementar alertas automatizadas"
  ]
}''',
                'mime_type': 'application/json'
            },
            {
                'name': 'configuracion.csv',
                'content': '''parametro,valor,descripcion
timeout,30,Tiempo limite en segundos
max_intentos,3,Numero maximo de reintentos
debug,true,Activar modo debug
formato_salida,json,Formato de respuesta
idioma,es,Idioma de la interfaz''',
                'mime_type': 'text/csv'
            },
            {
                'name': 'log_sistema.log',
                'content': '''[2025-01-15 10:30:15] INFO: Sistema iniciado correctamente
[2025-01-15 10:30:16] INFO: Cargando configuración desde archivo
[2025-01-15 10:30:17] INFO: Conectando a base de datos
[2025-01-15 10:30:18] INFO: Base de datos conectada exitosamente
[2025-01-15 10:30:19] INFO: Iniciando procesamiento de datos
[2025-01-15 10:31:45] INFO: Procesamiento completado - 985/1000 registros
[2025-01-15 10:31:46] WARN: 15 registros fallaron en validación
[2025-01-15 10:31:47] INFO: Generando reporte final
[2025-01-15 10:31:48] INFO: Reporte guardado en /tmp/reporte.txt''',
                'mime_type': 'text/plain'
            },
            {
                'name': 'script.py',
                'content': '''#!/usr/bin/env python3
"""
Script de análisis automatizado
Procesa datos y genera reportes
"""

import json
import csv
from datetime import datetime

def procesar_datos(archivo_entrada):
    """Procesa datos desde archivo de entrada"""
    resultados = {
        'total': 0,
        'procesados': 0,
        'errores': 0
    }
    
    print(f"Procesando archivo: {archivo_entrada}")
    
    # Simular procesamiento
    for i in range(1000):
        resultados['total'] += 1
        if i % 67 != 0:  # Simular algunos errores
            resultados['procesados'] += 1
        else:
            resultados['errores'] += 1
    
    return resultados

def generar_reporte(resultados):
    """Genera reporte en formato JSON"""
    reporte = {
        'timestamp': datetime.now().isoformat(),
        'resultados': resultados,
        'tasa_exito': resultados['procesados'] / resultados['total']
    }
    
    with open('reporte_final.json', 'w') as f:
        json.dump(reporte, f, indent=2)
    
    print("Reporte generado exitosamente")

if __name__ == "__main__":
    datos = procesar_datos("datos_entrada.csv")
    generar_reporte(datos)
    print("Procesamiento completado")''',
                'mime_type': 'text/x-python'
            }
        ]
        
        created_files = []
        
        for file_data in test_files_data:
            file_path = test_dir / file_data['name']
            
            # Escribir contenido del archivo
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_data['content'])
            
            # Crear información del archivo
            file_info = {
                'id': str(uuid.uuid4()),
                'name': file_data['name'],
                'path': str(file_path),
                'size': len(file_data['content'].encode('utf-8')),
                'type': 'file',
                'mime_type': file_data['mime_type'],
                'created_at': datetime.now().isoformat()
            }
            
            created_files.append(file_info)
        
        # Agregar archivos a la tarea
        if task_id not in task_files:
            task_files[task_id] = []
        
        # Marcar archivos del agente con source='agent'
        for file_info in created_files:
            file_info['source'] = 'agent'
        
        task_files[task_id].extend(created_files)
        
        return jsonify({
            'success': True,
            'message': f'Created {len(created_files)} test files',
            'files': created_files,
            'task_id': task_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500