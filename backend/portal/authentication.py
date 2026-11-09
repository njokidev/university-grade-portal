from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    """Token authentication where tokens expire, and locked accounts are
    rejected immediately even if they still hold a valid token."""

    keyword = "Bearer"

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        age = timezone.now() - token.created
        if age > timedelta(minutes=settings.SESSION_TOKEN_MINUTES):
            token.delete()
            raise AuthenticationFailed("Session expired. Please log in again.")
        if user.is_locked:
            token.delete()
            raise AuthenticationFailed("This account is locked.")
        return user, token
