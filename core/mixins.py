from core.models import RequestLog


class RequestLogMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        user = request.user if request.user.is_authenticated else None
        RequestLog.objects.create(
            user=user,
            endpoint=request.path,
            status=response.status_code,
        )

        return response


class ThrottleFinalizeMixin:
    """
    this is useful for views that have throttling enabled, and we want
    to rollback the throttle count if the response is not successful (e.g. 4xx or 5xx)
    """

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        for throttle_class in self.throttle_classes:
            if hasattr(throttle_class, "finalize_response"):
                throttle_class.finalize_response(request, response, self)

        return response
