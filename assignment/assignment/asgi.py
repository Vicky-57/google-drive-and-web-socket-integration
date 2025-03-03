import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import auth_test.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'assignment.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            auth_test.routing.websocket_urlpatterns
        )
    ),
})