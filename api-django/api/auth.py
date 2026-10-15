"""Authentification par token signé (pas de table de sessions, rien à stocker en base)."""
from django.conf import settings
from django.core import signing
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from .models import User

SALT = 'campuseats.login'


def make_token(user):
    return signing.dumps({'id_user': user.id_user}, salt=SALT)


class TokenAuthentication(BaseAuthentication):
    """Header attendu : Authorization: Bearer <token>"""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b'bearer':
            return None
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed('Header Authorization invalide.')
        try:
            data = signing.loads(parts[1].decode(), salt=SALT, max_age=settings.TOKEN_MAX_AGE)
            user = User.objects.select_related('role').get(pk=data['id_user'])
        except (signing.BadSignature, User.DoesNotExist):
            raise exceptions.AuthenticationFailed('Token invalide ou expiré.')
        return user, None

    def authenticate_header(self, request):
        return 'Bearer'
