# finanzas/tasks.py
import os
import json
from io import BytesIO
from decimal import Decimal
from datetime import datetime
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from allauth.socialaccount.models import SocialApp
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from PIL import Image
import google.generativeai as genai
from .models import registro_transacciones, TransaccionPendiente


def get_folder_id(drive_service, folder_name: str, parent_folder_id: str = 'root'):
    try:
        query = f"name='{folder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        response = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])
        return files[0]['id'] if files else None
    except HttpError as error:
        print(f"Ocurrió un error al buscar la carpeta '{folder_name}': {error}")
        return None

def move_file_to_processed(drive_service, file_id, original_folder_id):
    processed_folder_id = get_folder_id(drive_service, 'Procesados', parent_folder_id=original_folder_id)
    if not processed_folder_id:
        print("Creando carpeta 'Procesados'...")
        file_metadata = {
            'name': 'Procesados',
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [original_folder_id]
        }
        processed_folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        processed_folder_id = processed_folder.get('id')
    try:
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        drive_service.files().update(
            fileId=file_id,
            addParents=processed_folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        print(f"Archivo {file_id} movido a la carpeta 'Procesados'.")
    except HttpError as error:
        print(f"Ocurrió un error al mover el archivo: {error}")


@shared_task
def procesar_tickets_drive(user_id, auth_token, refresh_token):
    print(f"--- Iniciando procesamiento de tickets para el usuario ID: {user_id} ---")
    try:
        app = SocialApp.objects.get(provider='google')
        usuario = User.objects.get(id=user_id)

        creds = Credentials(
            token=auth_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=app.client_id,
            client_secret=app.secret
        )
        drive_service = build('drive', 'v3', credentials=creds)
        print("Conexión con Google Drive API exitosa.")

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-1.5-flash")

        folder_to_check = "Tickets de Compra" 
        folder_id = get_folder_id(drive_service, folder_to_check)
        
        if not folder_id:
            print(f"El usuario no tiene una carpeta llamada '{folder_to_check}'. Finalizando tarea.")
            return

        query = f"'{folder_id}' in parents and (mimeType='image/jpeg' or mimeType='image/png') and trashed=false"
        results = drive_service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            print("No se encontraron nuevos tickets para procesar.")
            return {'status': 'NO_FILES', 'message': 'No se encontraron nuevos tickets en tu Drive.'}

        print(f"Se encontraron {len(items)} tickets. Procesando...")
        for item in items:
            print(f"\nProcesando archivo: {item['name']} (ID: {item['id']})")
            file_id = item['id']

            request = drive_service.files().get_media(fileId=file_id)
            file_content = BytesIO(request.execute())
            image = Image.open(file_content)

            prompt = """
                    Eres un asistente experto en contabilidad para un sistema de finanzas personales.
                    Tu tarea es analizar la imagen de un documento y extraer la información clave con la máxima precisión.
                    Devuelve SIEMPRE la respuesta en formato JSON, sin absolutamente ningún texto adicional.

                    ### CONTEXTO:
                    El usuario ha subido una imagen de un ticket de compra o un comprobante de transferencia.
                    Necesito que identifiques el tipo de documento y extraigas los siguientes campos:

                    ### FORMATO DE SALIDA ESTRICTO (JSON):
                    {
                    "tipo_documento": "(TICKET_COMPRA|TRANSFERENCIA|OTRO)",
                    "fecha": "YYYY-MM-DD",
                    "establecimiento": "Nombre del comercio o beneficiario",
                    "descripcion_corta": "Un resumen breve del gasto (ej. 'Renta depto', 'Supermercado', 'Cena con amigos')",
                    "total": 0.00,
                    "confianza_extraccion": "(ALTA|MEDIA|BAJA)"
                    }
                    
                    ### REGLAS DE EXTRACCIÓN:
                    1.  **fecha**: Busca la fecha principal. Si no la encuentras, usa la fecha actual. Formato YYYY-MM-DD.
                    2.  **establecimiento**: El nombre principal de la tienda (ej. "Walmart", "Starbucks", "CFE"). Si es una transferencia, el nombre del beneficiario.
                    3.  **descripcion_corta**: Si es un ticket con muchos artículos, pon "Supermercado" o "Compra tienda". Si es una transferencia, usa el concepto.
                    4.  **total**: El monto TOTAL final. Debe ser un número (float), sin el símbolo de moneda.
                    5.  **confianza_extraccion**: Evalúa tu propia certeza.
                        - **ALTA**: Si la imagen es clara y todos los campos son obvios.
                        - **MEDIA**: Si la imagen es un poco borrosa o un campo es ambiguo.
                        - **BAJA**: Si la imagen es muy difícil de leer o faltan datos clave.

                    ### EJEMPLOS:
                    - **Ejemplo 1 (Ticket claro):**
                    { "tipo_documento": "TICKET_COMPRA", "fecha": "2025-07-03", "establecimiento": "La Comer", "descripcion_corta": "Supermercado", "total": 854.50, "confianza_extraccion": "ALTA" }
                    - **Ejemplo 2 (Transferencia):**
                    { "tipo_documento": "TRANSFERENCIA", "fecha": "2025-07-01", "establecimiento": "Juan Pérez", "descripcion_corta": "Renta Julio", "total": 7500.00, "confianza_extraccion": "ALTA" }
                    - **Ejemplo 3 (Ticket borroso):**
                    { "tipo_documento": "TICKET_COMPRA", "fecha": "2025-06-28", "establecimiento": "Restaurante El Sol", "descripcion_corta": "Comida", "total": 450.00, "confianza_extraccion": "MEDIA" }

                    Ahora, analiza la siguiente imagen:
            """
            
            response = model.generate_content([prompt, image])
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(cleaned_response)
                
                # 4. GUARDAR EN LA TABLA TEMPORAL:
                # Ahora creamos un objeto TransaccionPendiente
                TransaccionPendiente.objects.create(
                    propietario=usuario,
                    datos_json=data,
                    estado='pendiente'
                )
                print(f"¡Éxito! Ticket '{item['name']}' guardado como pendiente para revisión.")
                
                # ... (el resto del código para mover el archivo en Drive se queda igual) ...

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Error al procesar o guardar datos del ticket '{item['name']}': {e}")
                print(f"Respuesta de Gemini que causó el error: {cleaned_response}")

    except Exception as e:
        print(f"Ocurrió un error inesperado en la tarea Celery: {type(e).__name__} - {e}")
        # En caso de un error mayor, también devolvemos un estado claro
        return {'status': 'ERROR', 'message': str(e)}

    return f"Procesamiento finalizado para el usuario {user_id}."