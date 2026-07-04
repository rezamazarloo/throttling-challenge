from rest_framework import serializers

from communication.models import IncomingMessage


class IncomingMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomingMessage
        fields = ("id", "content", "created_at")
        read_only_fields = ("id", "created_at")
