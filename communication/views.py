from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated

from communication.models import IncomingMessage
from communication.serializers import IncomingMessageSerializer


class IncomingMessageCreateView(CreateAPIView):
    queryset = IncomingMessage.objects.all()
    serializer_class = IncomingMessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
