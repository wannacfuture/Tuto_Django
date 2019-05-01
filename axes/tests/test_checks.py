from django.core.checks import run_checks, Error
from django.test import override_settings, modify_settings

from axes.checks import Messages, Hints, Codes
from axes.conf import settings
from axes.tests.base import AxesTestCase


class CacheCheckTestCase(AxesTestCase):
    @override_settings(
        AXES_HANDLER='axes.handlers.cache.AxesCacheHandler',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.db.DatabaseCache', 'LOCATION': 'axes_cache'}},
    )
    def test_cache_check(self):
        errors = run_checks()
        self.assertEqual([], errors)

    @override_settings(
        AXES_HANDLER='axes.handlers.cache.AxesCacheHandler',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    def test_cache_check_errors(self):
        errors = run_checks()
        error = Error(
            msg=Messages.CACHE_INVALID,
            hint=Hints.CACHE_INVALID,
            obj=settings.CACHES,
            id=Codes.CACHE_INVALID,
        )

        self.assertEqual([error], errors)

    @override_settings(
        AXES_HANDLER='axes.handlers.database.AxesDatabaseHandler',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    def test_cache_check_does_not_produce_check_errors_with_database_handler(self):
        errors = run_checks()
        self.assertEqual([], errors)


class MiddlewareCheckTestCase(AxesTestCase):
    @modify_settings(
        MIDDLEWARE={
            'remove': ['axes.middleware.AxesMiddleware']
        },
    )
    def test_cache_check_errors(self):
        errors = run_checks()
        error = Error(
            msg=Messages.MIDDLEWARE_INVALID,
            hint=Hints.MIDDLEWARE_INVALID,
            obj=settings.MIDDLEWARE,
            id=Codes.MIDDLEWARE_INVALID,
        )

        self.assertEqual([error], errors)


class BackendCheckTestCase(AxesTestCase):
    @modify_settings(
        AUTHENTICATION_BACKENDS={
            'remove': ['axes.backends.AxesBackend']
        },
    )
    def test_cache_check_errors(self):
        errors = run_checks()
        error = Error(
            msg=Messages.BACKEND_INVALID,
            hint=Hints.BACKEND_INVALID,
            obj=settings.AUTHENTICATION_BACKENDS,
            id=Codes.BACKEND_INVALID,
        )

        self.assertEqual([error], errors)
