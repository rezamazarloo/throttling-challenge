import json

from core.models import RequestLog


class RequestLogMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        user = request.user if request.user.is_authenticated else None
        RequestLog.objects.create(
            user=user,
            method=request.method,
            endpoint=request.path,
            request_body=self.get_request_log_body(request),
            response_body=self.get_response_log_body(response),
            status=response.status_code,
        )

        return response

    def get_request_log_body(self, request):
        try:
            return self.serialize_log_body(request.data)
        except Exception:
            return None

    def get_response_log_body(self, response):
        return self.serialize_log_body(getattr(response, "data", None))

    def serialize_log_body(self, value):
        if value is None or value == "":
            return None

        if hasattr(value, "dict"):
            value = value.dict()

        try:
            return json.loads(json.dumps(value, default=str))
        except TypeError:
            return str(value)


class ThrottleFinalizeMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        # Give throttles a response-stage hook, e.g. to roll back non-2xx responses.
        for throttle_class in self.throttle_classes:
            if hasattr(throttle_class, "finalize_response"):
                throttle_class.finalize_response(request, response, self)

        return response
