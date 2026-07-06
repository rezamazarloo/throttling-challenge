import time
import threading
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITransactionTestCase

from communication.models import IncomingMessage
from communication.throttles import IncomingMessageRateThrottle
from core.models import RequestLog


@override_settings(
    USER_MESSAGE_RATE_LIMIT_COUNT=5,
    USER_MESSAGE_RATE_LIMIT_WINDOW_SECONDS=60,
)
class IncomingMessageEndpointTests(APITransactionTestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user_a = user_model.objects.create_user(
            username="user-a",
            password="test-pass-123",
        )
        self.user_b = user_model.objects.create_user(
            username="user-b",
            password="test-pass-123",
        )
        self.url = reverse("communication:incoming-messages")
        self.view_name = "communication:incoming-messages"
        self.redis = IncomingMessageRateThrottle.get_redis_client()
        self.clear_throttle_keys()

    def tearDown(self):
        self.clear_throttle_keys()
        close_old_connections()

    def test_allows_up_to_5_requests(self):
        responses = [self.create_message(self.user_a, index) for index in range(5)]

        self.assertEqual(
            [response.status_code for response in responses],
            [status.HTTP_201_CREATED] * 5,
        )
        self.assertEqual(IncomingMessage.objects.filter(user=self.user_a).count(), 5)

    def test_rejects_6th_request(self):
        for index in range(5):
            self.assertEqual(
                self.create_message(self.user_a, index).status_code,
                status.HTTP_201_CREATED,
            )

        response = self.create_message(self.user_a, 6)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(IncomingMessage.objects.filter(user=self.user_a).count(), 5)

    def test_allows_after_window_expires(self):
        for index in range(5):
            self.create_message(self.user_a, index)

        self.expire_window(self.user_a)
        response = self.create_message(self.user_a, 6)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IncomingMessage.objects.filter(user=self.user_a).count(), 6)

    def test_separate_limits_per_user(self):
        responses = []

        for index in range(5):
            responses.append(self.create_message(self.user_a, index))
            responses.append(self.create_message(self.user_b, index))

        self.assertEqual(
            [response.status_code for response in responses],
            [status.HTTP_201_CREATED] * 10,
        )
        self.assertEqual(IncomingMessage.objects.filter(user=self.user_a).count(), 5)
        self.assertEqual(IncomingMessage.objects.filter(user=self.user_b).count(), 5)

    def test_boundary_60_seconds(self):
        for index in range(4):
            self.create_message(self.user_a, index)

        self.redis.expire(self.throttle_key(self.user_a), 1)
        self.assertEqual(
            self.create_message(self.user_a, 5).status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            self.create_message(self.user_a, 6).status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

        self.expire_window(self.user_a)
        self.assertEqual(
            self.create_message(self.user_a, 6).status_code,
            status.HTTP_201_CREATED,
        )

    def test_retry_after_in_response(self):
        for index in range(5):
            self.create_message(self.user_a, index)
        self.redis.expire(self.throttle_key(self.user_a), 60)

        response = self.create_message(self.user_a, 6)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response["Retry-After"], "60")
        self.assertIn("Retry after 60 seconds", str(response.data["detail"]))

    def test_create_message_success(self):
        response = self.create_message(self.user_a, 1, content="hello there")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["content"], "hello there")
        self.assertIn("id", response.data)
        self.assertIn("created_at", response.data)
        self.assertTrue(
            IncomingMessage.objects.filter(
                user=self.user_a,
                content="hello there",
            ).exists()
        )

    def test_create_message_rate_limited(self):
        for index in range(5):
            self.create_message(self.user_a, index)

        response = self.create_message(self.user_a, 6, content="blocked")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertFalse(
            IncomingMessage.objects.filter(
                user=self.user_a,
                content="blocked",
            ).exists()
        )

    def test_request_log_created(self):
        response = self.create_message(self.user_a, 1, content="logged")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log = RequestLog.objects.get()
        self.assertEqual(log.user, self.user_a)
        self.assertEqual(log.method, "POST")
        self.assertEqual(log.endpoint, self.url)
        self.assertEqual(log.status, status.HTTP_201_CREATED)
        self.assertEqual(log.request_body, {"content": "logged"})
        self.assertEqual(log.response_body["content"], "logged")

    def test_staggered_requests_allow_after_first_request_window_expires(self):
        self.assertEqual(
            self.create_message(self.user_a, 1).status_code,
            status.HTTP_201_CREATED,
        )

        throttle_key = self.throttle_key(self.user_a)
        self.redis.expire(throttle_key, 30)
        for index in range(2, 6):
            self.assertEqual(
                self.create_message(self.user_a, index).status_code,
                status.HTTP_201_CREATED,
            )

        self.assertLessEqual(self.redis.ttl(throttle_key), 30)
        self.expire_window(self.user_a)
        self.assertEqual(
            self.create_message(self.user_a, 6).status_code,
            status.HTTP_201_CREATED,
        )

    def test_concurrent_requests_do_not_exceed_rate_limit(self):
        request_count = 10
        start_barrier = threading.Barrier(request_count)

        def send(index):
            close_old_connections()
            try:
                start_barrier.wait(timeout=5)
                return self.create_message(self.user_a, index).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=request_count) as executor:
            statuses = list(executor.map(send, range(request_count)))

        self.assertEqual(statuses.count(status.HTTP_201_CREATED), 5)
        self.assertEqual(statuses.count(status.HTTP_429_TOO_MANY_REQUESTS), 5)
        self.assertEqual(IncomingMessage.objects.filter(user=self.user_a).count(), 5)

    def create_message(self, user, index, content=None):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.post(
            self.url,
            {"content": content or f"message {index}"},
            format="json",
        )

    def throttle_key(self, user):
        return f"throttle:{self.view_name}:user:{user.pk}"

    def clear_throttle_keys(self):
        self.redis.delete(
            self.throttle_key(self.user_a),
            self.throttle_key(self.user_b),
        )

    def expire_window(self, user):
        key = self.throttle_key(user)
        self.redis.pexpire(key, 1)
        deadline = time.monotonic() + 1
        while self.redis.exists(key):
            if time.monotonic() > deadline:
                self.fail(f"Throttle key did not expire: {key}")
            time.sleep(0.01)
