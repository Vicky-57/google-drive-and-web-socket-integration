from django.contrib import admin
from django.urls import path,include
from django.shortcuts import redirect

def root_redirect(request):
    return redirect('login_page')

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("auth_test.urls")),
    path('', root_redirect),
    path('', include('auth_test.urls')),
]
