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
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        # Give throttles a response-stage hook, e.g. to roll back non-2xx responses.
        for throttle_class in self.throttle_classes:
            if hasattr(throttle_class, "finalize_response"):
                throttle_class.finalize_response(request, response, self)

        return response
