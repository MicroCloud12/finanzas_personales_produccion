import logging
from PIL import Image
from celery import shared_task, group
from django.contrib.auth.models import User
from .services import GoogleDriveService, GeminiService, TransactionService


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_single_ticket(self, user_id: int, file_id: str, file_name: str):
    """
    Procesa un único ticket: lo descarga, lo analiza con Gemini y lo guarda como pendiente.
    Utiliza los servicios para abstraer la lógica.
    """
    try:
        user = User.objects.get(id=user_id)
        
        # 1. Usar servicios
        gdrive_service = GoogleDriveService(user)
        gemini_service = GeminiService()
        transaction_service = TransactionService()

        # 2. Obtener contenido del archivo
        file_content = gdrive_service.get_file_content(file_id)
        image = Image.open(file_content)

        # 3. Extraer datos con Gemini
        extracted_data = gemini_service.extract_data_from_image(image)

        # 4. Crear transacción pendiente
        transaction_service.create_pending_transaction(user, extracted_data)

        # (Opcional) Aquí podrías añadir la lógica para mover el archivo a una carpeta "Procesados"
        # gdrive_service.move_file_to_processed(file_id, ...)
        
        return {'status': 'SUCCESS', 'file_name': file_name}

    except ConnectionError as e:
        # Error de conexión (ej. token no válido), no reintentar.
        self.update_state(state='FAILURE', meta=str(e))
        return {'status': 'FAILURE', 'file_name': file_name, 'error': 'ConnectionError'}
    except Exception as e:
        # Para otros errores, reintentar
        self.retry(exc=e)
        return {'status': 'FAILURE', 'file_name': file_name, 'error': str(e)}

@shared_task
def process_drive_tickets(user_id: int):
    """
    Tarea principal: Obtiene la lista de tickets y lanza tareas paralelas para procesarlos.
    """
    try:
        user = User.objects.get(id=user_id)
        gdrive_service = GoogleDriveService(user)
        files_to_process = gdrive_service.list_files_in_folder(
            folder_name="Tickets de Compra", 
            mimetypes=['image/jpeg', 'image/png']
        )

        if not files_to_process:
            return {'status': 'NO_FILES', 'message': 'No se encontraron nuevos tickets.'}

        job = group(
            process_single_ticket.s(user.id, item['id'], item['name'])
            for item in files_to_process
        )
        
        result_group = job.apply_async()
        result_group.save() # ¡Esto es clave! Guarda el estado del grupo en el backend de resultados.

        # --- CAMBIO IMPORTANTE ---
        # Devolvemos el ID del grupo para que el frontend pueda monitorearlo.
        return {'status': 'STARTED', 'task_group_id': result_group.id, 'total_tasks': len(files_to_process)}

    except Exception as e:
        # Manejo de errores
        return {'status': 'ERROR', 'message': str(e)}
