from django.conf import settings
from django.db import models


class RequestLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=False,
        related_name="request_logs",
    )
    endpoint = models.CharField(max_length=255)
    status = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"user #{self.user_id} | {self.endpoint} | {self.status}"
