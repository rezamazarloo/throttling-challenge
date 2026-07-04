from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated

from communication.models import IncomingMessage
from communication.serializers import (
    IncomingMessageCreateSerializer,
    IncomingMessageSerializer,
)
from communication.throttles import IncomingMessageRateThrottle
from core.mixins import RequestLogMixin, ThrottleFinalizeMixin


@extend_schema_view(
    post=extend_schema(
        request=IncomingMessageCreateSerializer,
        responses={
            status.HTTP_201_CREATED: IncomingMessageSerializer,
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="Rate limit exceeded. Retry after the returned number of seconds."
            ),
        },
    )
)
class IncomingMessageCreateView(
    RequestLogMixin,
    ThrottleFinalizeMixin,
    CreateAPIView,
):
    queryset = IncomingMessage.objects.all()
    serializer_class = IncomingMessageSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [IncomingMessageRateThrottle]

    def perform_create(self, serializer):
        return serializer.save(user=self.request.user)
