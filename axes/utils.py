from typing import Optional
from datetime import timedelta
from logging import getLogger
from socket import error, inet_pton, AF_INET6

from django.core.cache import caches, BaseCache
from django.http import HttpResponse, HttpResponseRedirect, HttpRequest, JsonResponse
from django.shortcuts import render
from django.utils.module_loading import import_string

import ipware.ip2

from axes.conf import settings
from axes.models import AccessAttempt

logger = getLogger(__name__)


def get_axes_cache() -> BaseCache:
    return caches[getattr(settings, 'AXES_CACHE', 'default')]


def query2str(dictionary: dict, max_length: int = 1024) -> str:
    """
    Turns a dictionary into an easy-to-read list of key-value pairs.

    If there is a field called password it will be excluded from the output.

    The length of the output is limited to max_length to avoid a DoS attack via excessively large payloads.
    """

    return '\n'.join([
        '%s=%s' % (k, v) for k, v in dictionary.items()
        if k != settings.AXES_PASSWORD_FORM_FIELD
    ][:int(max_length / 2)])[:max_length]


def get_client_str(username, ip_address, user_agent=None, path_info=None):
    if settings.AXES_VERBOSE:
        if path_info and isinstance(path_info, tuple):
            path_info = path_info[0]

        details = '{{user: "{0}", ip: "{1}", user-agent: "{2}", path: "{3}"}}'
        return details.format(username, ip_address, user_agent, path_info)

    if settings.AXES_ONLY_USER_FAILURES:
        client = username
    elif settings.AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP:
        client = '{0} from {1}'.format(username, ip_address)
    else:
        client = ip_address

    if settings.AXES_USE_USER_AGENT:
        client += '(user-agent={0})'.format(user_agent)

    return client


def get_client_ip(request: HttpRequest) -> str:
    client_ip_attribute = 'axes_client_ip'

    if not hasattr(request, client_ip_attribute):
        client_ip, _ = ipware.ip2.get_client_ip(
            request,
            proxy_order=settings.AXES_PROXY_ORDER,
            proxy_count=settings.AXES_PROXY_COUNT,
            proxy_trusted_ips=settings.AXES_PROXY_TRUSTED_IPS,
            request_header_order=settings.AXES_META_PRECEDENCE_ORDER,
        )
        setattr(request, client_ip_attribute, client_ip)
    return getattr(request, client_ip_attribute)


def get_client_username(request: HttpRequest, credentials: dict = None) -> str:
    """
    Resolve client username from the given request or credentials if supplied.

    The order of preference for fetching the username is as follows:

    1. If configured, use ``AXES_USERNAME_CALLABLE``, and supply ``request, credentials`` as arguments
    2. If given, use ``credentials`` and fetch username from ``AXES_USERNAME_FORM_FIELD`` (defaults to ``username``)
    3. Use request.POST and fetch username from ``AXES_USERNAME_FORM_FIELD`` (defaults to ``username``)

    :param request: incoming Django ``HttpRequest`` or similar object from authentication backend or other source
    :param credentials: incoming credentials ``dict`` or similar object from authentication backend or other source
    """

    if settings.AXES_USERNAME_CALLABLE:
        logger.debug('Using settings.AXES_USERNAME_CALLABLE to get username')

        if callable(settings.AXES_USERNAME_CALLABLE):
            return settings.AXES_USERNAME_CALLABLE(request, credentials)
        if isinstance(settings.AXES_USERNAME_CALLABLE, str):
            return import_string(settings.AXES_USERNAME_CALLABLE)(request, credentials)
        raise TypeError('settings.AXES_USERNAME_CALLABLE needs to be a string, callable, or None.')

    if credentials:
        logger.debug('Using parameter credentials to get username with key settings.AXES_USERNAME_FORM_FIELD')
        return credentials.get(settings.AXES_USERNAME_FORM_FIELD, None)

    logger.debug('Using parameter request.POST to get username with key settings.AXES_USERNAME_FORM_FIELD')
    return request.POST.get(settings.AXES_USERNAME_FORM_FIELD, None)


def get_client_user_agent(request: HttpRequest) -> str:
    return request.META.get('HTTP_USER_AGENT', '<unknown>')[:255]


def get_credentials(username: str = None, **kwargs):
    credentials = {settings.AXES_USERNAME_FORM_FIELD: username}
    credentials.update(kwargs)
    return credentials


def get_cool_off() -> Optional[timedelta]:
    """
    Return the login cool off time interpreted from settings.AXES_COOLOFF_TIME.

    The return value is either None or timedelta.

    Notice that the settings.AXES_COOLOFF_TIME is either None, timedelta, or integer of hours,
    and this function offers a unified _timedelta or None_ representation of that configuration
    for use with the Axes internal implementations.

    :exception TypeError: if settings.AXES_COOLOFF_TIME is of wrong type.
    """

    cool_off = settings.AXES_COOLOFF_TIME

    if isinstance(cool_off, int):
        return timedelta(hours=cool_off)
    return cool_off


def get_cache_timeout() -> Optional[int]:
    """
    Return the cache timeout interpreted from settings.AXES_COOLOFF_TIME.

    The cache timeout can be either None if not configured or integer of seconds if configured.

    Notice that the settings.AXES_COOLOFF_TIME can be None, timedelta, or integer of hours,
    and this function offers a unified _integer or None_ representation of that configuration
    for use with the Django cache backends.
    """

    cool_off = get_cool_off()
    if cool_off is None:
        return None
    return int(cool_off.total_seconds())


def is_ipv6(ip: str):
    try:
        inet_pton(AF_INET6, ip)
    except (OSError, error):
        return False
    return True


def reset(ip: str = None, username: str = None):
    """
    Reset records that match IP or username, and return the count of removed attempts.
    """

    attempts = AccessAttempt.objects.all()
    if ip:
        attempts = attempts.filter(ip_address=ip)
    if username:
        attempts = attempts.filter(username=username)

    count, _ = attempts.delete()

    return count


def iso8601(delta: timedelta) -> str:
    """
    Return datetime.timedelta translated to ISO 8601 formatted duration.
    """

    seconds = delta.total_seconds()
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    date = '{:.0f}D'.format(days) if days else ''

    time_values = hours, minutes, seconds
    time_designators = 'H', 'M', 'S'

    time = ''.join([
        ('{:.0f}'.format(value) + designator)
        for value, designator in zip(time_values, time_designators)
        if value]
    )
    return 'P' + date + ('T' + time if time else '')


def get_lockout_message() -> str:
    if settings.AXES_COOLOFF_TIME:
        return settings.AXES_COOLOFF_MESSAGE
    return settings.AXES_PERMALOCK_MESSAGE


def get_lockout_response(request: HttpRequest) -> HttpResponse:
    context = {
        'failure_limit': settings.AXES_FAILURE_LIMIT,
        'username': get_client_username(request) or ''
    }

    cool_off = settings.AXES_COOLOFF_TIME
    if cool_off:
        if isinstance(cool_off, (int, float)):
            cool_off = timedelta(hours=cool_off)

        context.update({
            'cooloff_time': iso8601(cool_off)
        })

    status = 403

    if request.is_ajax():
        return JsonResponse(
            context,
            status=status,
        )

    if settings.AXES_LOCKOUT_TEMPLATE:
        return render(
            request,
            settings.AXES_LOCKOUT_TEMPLATE,
            context,
            status=status,
        )

    if settings.AXES_LOCKOUT_URL:
        return HttpResponseRedirect(settings.AXES_LOCKOUT_URL)

    return HttpResponse(get_lockout_message(), status=status)
