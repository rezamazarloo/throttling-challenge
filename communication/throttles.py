from core.throttles import RedisUserViewRateThrottle


class IncomingMessageRateThrottle(RedisUserViewRateThrottle):
    count_success_only = True
    limit_setting = "USER_MESSAGE_RATE_LIMIT_COUNT"
    window_setting = "USER_MESSAGE_RATE_LIMIT_WINDOW_SECONDS"
