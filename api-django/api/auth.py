"""Authentification : mots de passe en Argon2id, session par token JWT (HS256)."""
import time

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from .models import User

ALGORITHM = 'HS256'

# Argon2id, format standard "$argon2id$v=19$m=...,t=...,p=...$sel$hash"
# (le même que PHP password_hash(..., PASSWORD_ARGON2ID) côté Symfony)
password_hasher = PasswordHasher()


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(stored_hash, password):
    try:
        return password_hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def make_token(user):
    """Renvoie (token JWT, durée de validité en secondes)."""
    now = int(time.time())
    expires_in = settings.JWT_EXPIRES_IN
    payload = {'sub': str(user.id_user), 'iat': now, 'exp': now + expires_in}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM), expires_in


class JWTAuthentication(BaseAuthentication):
    """Header attendu : Authorization: Bearer <jwt>"""

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b'bearer':
            return None
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed('Header Authorization invalide.')
        try:
            payload = jwt.decode(parts[1].decode(), settings.SECRET_KEY, algorithms=[ALGORITHM],
                                 options={'require': ['exp', 'sub']})
            user = User.objects.select_related('role').get(pk=int(payload['sub']))
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token expiré.')
        except (jwt.InvalidTokenError, ValueError, User.DoesNotExist):
            raise exceptions.AuthenticationFailed('Token invalide.')
        return user, None

    def authenticate_header(self, request):
        return 'Bearer'
