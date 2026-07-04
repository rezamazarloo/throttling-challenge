from django.urls import path

from communication.views import IncomingMessageCreateView

app_name = "communication"

urlpatterns = [
    path("messages/", IncomingMessageCreateView.as_view(), name="incoming-messages"),
]
