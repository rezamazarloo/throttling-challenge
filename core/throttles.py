import math

from django.conf import settings
from redis import Redis, RedisError
from rest_framework.exceptions import APIException, NotAuthenticated, Throttled
from rest_framework.throttling import BaseThrottle


class ThrottleStorageUnavailable(APIException):
    status_code = 503
    default_detail = "Throttling is temporarily unavailable."
    default_code = "throttle_storage_unavailable"


class RedisUserRateThrottle(BaseThrottle):
    """
    1- use include_view_name = True to add per view rate limit, by adding
    view name to redis key.

    2- use count_success_only = True to only count successful requests (2xx)
    and rollback the count for failed requests (4xx, 5xx).
    to do this we need to use ThrottleFinalizeMixin in the view.

    3- request_key_attr stores the reserved redis key on the current request
    so rollback can find it and avoid rolling back twice(double rollback).

    4- reserve_request() method is used to reserve a request and returns
    (allowed, wait). Throttled responses are raised from allow_request().
    """

    count_success_only = False
    include_view_name = False
    limit_setting = "USER_RATE_LIMIT_COUNT"
    window_setting = "USER_RATE_LIMIT_WINDOW_SECONDS"
    request_key_attr = "_redis_throttle_key"
    reserve_script = """
    local current = tonumber(redis.call("GET", KEYS[1]) or "0")
    local limit = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])

    if current >= limit then
        local ttl = redis.call("TTL", KEYS[1])
        if ttl < 0 then
            redis.call("EXPIRE", KEYS[1], window)
            ttl = window
        end
        return {0, current, ttl}
    end

    if current == 0 then
        redis.call("SET", KEYS[1], 1, "EX", window)
        return {1, 1, window}
    end

    local new_count = redis.call("INCR", KEYS[1])
    local ttl = redis.call("TTL", KEYS[1])
    if ttl < 0 then
        redis.call("EXPIRE", KEYS[1], window)
        ttl = window
    end
    return {1, new_count, ttl}
    """
    rollback_script = """
    local current = tonumber(redis.call("GET", KEYS[1]) or "0")
    if current <= 1 then
        redis.call("DEL", KEYS[1])
        return 0
    end
    return redis.call("DECR", KEYS[1])
    """

    def allow_request(self, request, view):
        if not self.should_throttle(request):
            raise NotAuthenticated("Authentication is required for this throttle.")

        allowed, wait = type(self).reserve_request(request, view)
        self._wait = wait
        if not allowed:
            raise Throttled(wait=wait, detail=type(self).get_throttled_detail(wait))

        return True

    def wait(self):
        return getattr(self, "_wait", None)

    @classmethod
    def reserve_request(cls, request, view):
        key = cls.get_cache_key(request, view)

        try:
            allowed, _count, ttl = cls.get_redis_client().eval(
                cls.reserve_script,
                1,
                key,
                cls.get_limit(),
                cls.get_window_seconds(),
            )
            if int(allowed):
                setattr(request, cls.request_key_attr, key)
                return True, None
        except RedisError as exc:
            raise ThrottleStorageUnavailable() from exc

        wait = cls.normalize_ttl(ttl)
        return False, wait

    @classmethod
    def rollback_request(cls, request):
        key = getattr(request, cls.request_key_attr, None)
        if not key:
            return

        try:
            cls.rollback_key(key)
        except RedisError as exc:
            raise ThrottleStorageUnavailable() from exc
        finally:
            setattr(request, cls.request_key_attr, None)

    @classmethod
    def finalize_response(cls, request, response, view):
        if cls.count_success_only and not cls.is_success_response(response):
            cls.rollback_request(request)

    @classmethod
    def get_cache_key(cls, request, view):
        parts = ["throttle"]
        if cls.include_view_name:
            parts.append(cls.get_view_name(request, view))
        parts.extend(["user", str(request.user.pk)])
        return ":".join(parts)

    @classmethod
    def get_view_name(cls, request, view):
        view_name = getattr(request.resolver_match, "view_name", None)
        if view_name:
            return view_name
        return view.__class__.__name__ if view else cls.__name__

    @classmethod
    def get_limit(cls):
        return int(getattr(settings, cls.limit_setting))

    @classmethod
    def get_window_seconds(cls):
        return int(getattr(settings, cls.window_setting))

    @classmethod
    def get_redis_client(cls):
        return Redis.from_url(settings.REDIS_URL, decode_responses=True)

    @classmethod
    def get_usage(cls, key):
        try:
            count, ttl = cls.get_redis_client().pipeline().get(key).ttl(key).execute()
        except RedisError as exc:
            raise ThrottleStorageUnavailable() from exc
        return int(count or 0), ttl

    @classmethod
    def rollback_key(cls, key):
        cls.get_redis_client().eval(cls.rollback_script, 1, key)

    @classmethod
    def get_throttled_detail(cls, wait):
        seconds = math.ceil(wait)
        return f"Rate limit exceeded. Retry after {seconds} seconds."

    @classmethod
    def normalize_ttl(cls, ttl):
        if ttl is None or ttl < 0:
            return cls.get_window_seconds()
        return max(1, int(ttl))

    @classmethod
    def is_success_response(cls, response):
        return 200 <= response.status_code < 300

    def should_throttle(self, request):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated)


class RedisUserViewRateThrottle(RedisUserRateThrottle):
    include_view_name = True
