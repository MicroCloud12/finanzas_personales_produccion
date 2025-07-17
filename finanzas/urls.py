from . import views
from django.urls import path
# Importamos las vistas de autenticación que Django nos regala
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('transacciones/', views.crear_transacciones, name='crear_transacciones'),
    path('registrousuarios/', views.registro, name='registro_usuarios'),
    path('login/', auth_views.LoginView.as_view(template_name='iniciosesion.html'), name='login'),
    # La LogoutView ahora usará automáticamente la variable LOGOUT_REDIRECT_URL de settings.py
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', views.vista_dashboard, name='dashboard'),
    path('listatransacciones/', views.lista_transacciones, name='lista_transacciones'),
    path('api/datos-gastos-categoria/', views.datos_gastos_categoria, name='api_datos_gastos'),
    path('api/datos-flujo-dinero/', views.datos_flujo_dinero, name='api_flujo_dinero'),
    path('procesamiento-automatico/', views.vista_procesamiento_automatico, name='procesamiento_automatico'),
    path('procesar-drive/', views.iniciar_procesamiento_drive, name='procesar_drive'),
    path('revisar-tickets/', views.revisar_tickets, name='revisar_tickets'),
    path('aprobar-ticket/<int:ticket_id>/', views.aprobar_ticket, name='aprobar_ticket'),
    path('rechazar-ticket/<int:ticket_id>/', views.rechazar_ticket, name='rechazar_ticket'),
    # 1. Una URL solo para obtener el resultado de la tarea inicial
    path('resultado-tarea-inicial/<str:task_id>/', views.get_initial_task_result, name='get_initial_task_result'),
    # 2. Una URL solo para monitorear el progreso del grupo
    path('estado-grupo/<str:group_id>/', views.get_group_status, name='get_group_status'),
    path('revisar_tickets/', views.revisar_tickets, name='revisar_tickets'),
# --- URLs para Inversiones ---
    path('inversiones/', views.lista_inversiones, name='lista_inversiones'),
    path('inversiones/crear/', views.crear_inversion, name='crear_inversion'),

    # --- URLs para Suscripción ---
    path('suscripcion/', views.gestionar_suscripcion, name='gestionar_suscripcion'),
    path('suscripcion/exitosa/', views.suscripcion_exitosa, name='suscripcion_exitosa'),
    path('suscripcion/fallida/', views.suscripcion_fallida, name='suscripcion_fallida'),
    path('suscripcion/webhook/', views.mercadopago_webhook, name='mercadopago_webhook'),
    # Aquí irá el webhook de MercadoPago que configuraremos al final para producción
    # path('suscripcion/webhook/', views.mercadopago_webhook, name='mercadopago_webhook'),
]