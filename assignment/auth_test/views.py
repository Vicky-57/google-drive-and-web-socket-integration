import json 
import io
from django.shortcuts import redirect, render
from urllib.parse import urlencode
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session


def get_sessions():
    sessions = Session.objects.all()
    for session in sessions:
        data = session.get_decoded()  
        print(data)  


def my_view(request):
    access_token = request.session.get('access_token')  
    if not access_token:
        return JsonResponse({'error': 'Access token not found'}, status=401)
    
    return JsonResponse({'token': access_token})


def home(request):
    if 'access_token' in request.session:
        if 'access_token' in request.session:
            return JsonResponse({"message": "Authenticated", "redirect": "pick_from_drive"})
        return JsonResponse({"error": "Not authenticated", "redirect": "google_login"}, status=401)


def login_page(request):
    return render(request, 'auth_test/login.html')


def chat_page(request, room_name="assessment_room"):
    if 'access_token' not in request.session:
        return redirect('google_login')
    return render(request, 'auth_test/chat.html', {'room_name': room_name})


def google_login(request):
    google_auth_url = "https://accounts.google.com/o/oauth2/auth"
    params = {
        "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
        "response_type": "code",
        "scope": "openid email profile https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/drive.file",
        "redirect_uri": settings.SOCIAL_AUTH_GOOGLE_REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent",
    }
    return redirect(f"{google_auth_url}?{urlencode(params)}")


def google_callback(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "No code provided"}, status=400)


    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
        "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.SOCIAL_AUTH_GOOGLE_REDIRECT_URI, 
    }
    
    response = requests.post(token_url, data=data)
    token_info = response.json()

    if "access_token" not in token_info:
        return JsonResponse({"error": "Invalid token response", "details": token_info}, status=400)

    user_info_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    headers = {"Authorization": f"Bearer {token_info['access_token']}"}    
    user_data = requests.get(user_info_url, headers=headers).json()


    if not request.session.session_key:
        request.session.create()
    

    request.session['access_token'] = token_info["access_token"]
    request.session['user_email'] = user_data.get('email')
    request.session['user_name'] = user_data.get('name')
    
    if "refresh_token" in token_info:
        request.session['refresh_token'] = token_info["refresh_token"]
    

    request.session.modified = True
    request.session.save()
    
    print(f"Session ID: {request.session.session_key}")
    print(f"Access token stored in session: {request.session.get('access_token')[:10]}...")
    print(f"Session contents: {dict(request.session)}")


    return redirect('pick_from_drive')


@csrf_exempt
def upload_to_drive(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)


    access_token = request.session.get("access_token")
    if not access_token:
        access_token = request.GET.get("access_token")
    
    file = request.FILES.get("file")

    if not access_token:
        return JsonResponse({"error": "Not authenticated. Please log in."}, status=401)
    
    if not file:
        return JsonResponse({"error": "No file provided"}, status=400)

    headers = {"Authorization": f"Bearer {access_token}"}
    metadata = {
        "name": file.name,
        "parents": ["root"]  
    }

    files = {
        "data": ("metadata", json.dumps(metadata), "application/json"),
        "file": (file.name, file, file.content_type),
    }

    drive_upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
    response = requests.post(drive_upload_url, headers=headers, files=files)

    if response.status_code == 200:
        return JsonResponse({"message": "File uploaded successfully", "file_info": response.json()})
    else:
        return JsonResponse({"error": "File upload failed", "details": response.text}, status=400)


@csrf_exempt
def list_drive_files(request):

    access_token = request.session.get("access_token")
    if not access_token:
        access_token = request.GET.get("access_token")  
    
    wants_json = request.headers.get('Accept') == 'application/json' or 'application/json' in request.headers.get('Accept', '')
    
    if not access_token:
        if wants_json:
            return JsonResponse({"error": "Not authenticated. Please log in."}, status=401)
        else:
            return redirect('google_login')
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    params = {
        "fields": "files(id, name, mimeType, size, webViewLink)",
        "q": "trashed=false",  
        "pageSize": 100
    }
    
    drive_files_url = "https://www.googleapis.com/drive/v3/files"
    response = requests.get(drive_files_url, headers=headers, params=params)
    
    if response.status_code == 200:
        if wants_json:
            return JsonResponse(response.json())
        else:
            files = response.json().get('files', [])
            return render(request, 'auth_test/files_list.html', {'files': files})
    
    elif response.status_code == 401:
        refresh_result = refresh_token(request)
        if isinstance(refresh_result, JsonResponse):
            return refresh_result
        
        access_token = request.session.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(drive_files_url, headers=headers, params=params)
        
        if response.status_code == 200:
            if wants_json:
                return JsonResponse(response.json())
            else:
                files = response.json().get('files', [])
                return render(request, 'auth_test/files_list.html', {'files': files})
        
    error_details = {"error": "Failed to fetch files", "status": response.status_code}
    try:
        error_details["details"] = response.json()
    except:
        error_details["details"] = response.text
    
    return JsonResponse(error_details, status=400)

@csrf_exempt
def download_file(request, file_id):

    access_token = request.session.get("access_token")
    if not access_token:
        access_token = request.GET.get("access_token")
    
    if not access_token:
        return JsonResponse({"error": "Not authenticated. Please log in."}, status=401)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    file_metadata_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name,mimeType"
    metadata_response = requests.get(file_metadata_url, headers=headers)
    
    if metadata_response.status_code != 200:
        return JsonResponse({"error": "Failed to fetch file metadata", "details": metadata_response.text}, status=400)
    
    file_metadata = metadata_response.json()
    file_name = file_metadata.get("name", "downloaded_file")
    
    download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    file_response = requests.get(download_url, headers=headers, stream=True)
    
    if file_response.status_code != 200:
        return JsonResponse({"error": "Failed to download file", "details": file_response.text}, status=400)
    

    response = HttpResponse(
        file_response.content,
        content_type=file_response.headers.get('Content-Type', 'application/octet-stream')
    )
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response


def debug_session(request):

    session_data = {
        'session_key': request.session.session_key,
        'has_access_token': 'access_token' in request.session,
        'full_access_token': request.session.get('access_token'),
        'token_preview': request.session.get('access_token', '')[:10] + '...' if request.session.get('access_token') else None,
        'user_email': request.session.get('user_email'),
        'session_keys': list(request.session.keys()),
    }
    return JsonResponse(session_data)

def pick_from_drive(request):

    access_token = request.session.get('access_token')
    if not access_token:
        print(f"Session ID: {request.session.session_key}")
        print(f"Session contents: {dict(request.session)}")
        return redirect('google_login')
    
    user_email = request.session.get('user_email', 'User')
    
    context = {
        'client_id': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
        'api_key': settings.SOCIAL_AUTH_GOOGLE_API_KEY,
        'app_id': settings.SOCIAL_AUTH_GOOGLE_APP_ID,
        'access_token': request.session.get('access_token'),
        'user_email': user_email
    }
    
    return render(request, 'auth_test/picker.html', context)



@csrf_exempt
def refresh_token(request):

    
    refresh_token = request.session.get('refresh_token')
    if not refresh_token:
        return JsonResponse({"error": "No refresh token available"}, status=400)
    
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
        "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    
    response = requests.post(token_url, data=data)
    token_info = response.json()
    
    if "access_token" not in token_info:
        return JsonResponse({"error": "Failed to refresh token", "details": token_info}, status=400)
    

    request.session['access_token'] = token_info["access_token"]
    
    print(f"Session ID: {request.session.session_key}")
    print(f"Session contents: {dict(request.session)}")
    
    request.session.modified = True
    request.session.save()
    

    print(f"Verifying token: {request.session.get('access_token')[:10]}...")
    
    return redirect('pick_from_drive')

def logout(request):
 
    

    request.session.pop('access_token', None)
    request.session.pop('refresh_token', None)
    request.session.pop('user_email', None)
    request.session.pop('user_name', None)
    
    return redirect('login_page')