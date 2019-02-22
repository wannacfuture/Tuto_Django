from unittest.mock import patch, MagicMock

from django.test import TestCase

from axes.backends import AxesBackend
from axes.exceptions import AxesBackendRequestParameterRequired, AxesBackendPermissionDenied


class BackendTestCase(TestCase):
    def test_authenticate_raises_on_missing_request(self):
        request = None

        with self.assertRaises(AxesBackendRequestParameterRequired):
            AxesBackend().authenticate(request)

    @patch('axes.handlers.proxy.AxesProxyHandler.is_allowed_to_authenticate', return_value=False)
    def test_authenticate_raises_on_locked_request(self, _):
        request = MagicMock()

        with self.assertRaises(AxesBackendPermissionDenied):
            AxesBackend().authenticate(request)
