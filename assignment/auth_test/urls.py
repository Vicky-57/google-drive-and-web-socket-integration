
from django.urls import path
from .views import (
    home, login_page, google_login, google_callback, 
    upload_to_drive, list_drive_files, download_file, 
    pick_from_drive, refresh_token, chat_page,debug_session
)

urlpatterns = [
    path('login/', login_page, name='login_page'),
    path('google/login/', google_login, name='google_login'),
    path('google/callback/', google_callback, name='google_callback'),
    path('google/upload/', upload_to_drive, name='upload_to_drive'),
    path('google/files/', list_drive_files, name='list_drive_files'),
    path('google/download/<str:file_id>/', download_file, name='download_file'),
    path('google/picker/', pick_from_drive, name='pick_from_drive'),
    path('google/refresh-token/', refresh_token, name='refresh_token'),
    path('chat/', chat_page, name='chat_page'),
    path('chat/<str:room_name>/', chat_page, name='chat_with_room'),
    path('debug-session/', debug_session, name='debug_session'),
]