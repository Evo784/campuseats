from datetime import date

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import analytics
from .auth import hash_password, make_token, verify_password
from .models import Menu, Order, Role, User
from .serializers import MenuSerializer, OrderSerializer


class UserCreateView(APIView):
    """POST /v1/users : inscription publique, crée toujours un compte USER (Argon2id)."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        password = str(request.data.get('password', ''))
        if '@' not in email or len(email) > 255:
            raise ValidationError({'email': 'Email invalide.'})
        if len(password) < 8:
            raise ValidationError({'password': '8 caractères minimum.'})
        if User.objects.filter(email=email).exists():
            return Response({'detail': 'Cet email est déjà utilisé.'}, status=status.HTTP_409_CONFLICT)
        user = User.objects.create(email=email, password_hash=hash_password(password),
                                   role=Role.objects.get(label='USER'))
        return Response({'id_user': user.id_user, 'email': user.email, 'role': 'USER'},
                        status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        password = str(request.data.get('password', ''))
        user = User.objects.filter(email=email).select_related('role').first()
        # Même message dans les deux cas : on ne révèle pas si l'email existe
        if user is None or not verify_password(user.password_hash, password):
            return Response({'detail': 'Email ou mot de passe incorrect.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        token, expires_in = make_token(user)
        return Response({'token': token, 'expires_in': expires_in})


class MenuByIdView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, id_menu):
        menu = get_object_or_404(Menu, pk=id_menu)
        return Response(MenuSerializer(menu).data)


class MenuListView(APIView):
    """GET /v1/menus?date=YYYY-MM-DD (sans date : aujourd'hui). Un seul menu par jour."""
    permission_classes = [AllowAny]

    def get(self, request):
        raw = request.query_params.get('date')
        try:
            day = date.fromisoformat(raw) if raw else date.today()
        except ValueError:
            raise ValidationError({'date': 'Format attendu : YYYY-MM-DD.'})
        menu = Menu.objects.filter(menu_date=day).first()
        if menu is None:
            raise Http404(f'Pas de menu pour le {day.isoformat()}.')
        return Response(MenuSerializer(menu).data)


class OrderCreateView(APIView):
    def post(self, request):
        serializer = OrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(user=request.user)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    def get(self, request, id_order):
        order = get_object_or_404(Order, pk=id_order)
        if order.user_id != request.user.id_user and not request.user.is_admin:
            raise PermissionDenied("Cette commande n'est pas à vous.")
        return Response(OrderSerializer(order).data)

    def patch(self, request, id_order):
        """Marquer une commande comme récupérée : {"is_delivered": true} (admin seulement)."""
        if not request.user.is_admin:
            raise PermissionDenied('Réservé à la cafétéria.')
        order = get_object_or_404(Order, pk=id_order)
        value = request.data.get('is_delivered')
        if not isinstance(value, bool):
            raise ValidationError({'is_delivered': 'Booléen attendu (true ou false).'})
        order.is_delivered = value
        order.save(update_fields=['is_delivered'])
        return Response(OrderSerializer(order).data)


def _period(request):
    """Lit startDate et endDate (YYYY-MM-DD) dans la query string."""
    try:
        start = date.fromisoformat(request.query_params['startDate'])
        end = date.fromisoformat(request.query_params['endDate'])
    except (KeyError, ValueError):
        raise ValidationError('Paramètres startDate et endDate requis, format YYYY-MM-DD.')
    if start > end:
        raise ValidationError('startDate doit être avant endDate.')
    return start, end


def _require_admin(request):
    if not request.user.is_admin:
        raise PermissionDenied('Réservé à la cafétéria.')


class DishStatsView(APIView):
    """GET /v1/dishes/stats?startDate=&endDate= (tout utilisateur connecté)."""

    def get(self, request):
        start, end = _period(request)
        return Response(analytics.dish_stats(start, end))


class OrderStatsView(APIView):
    """GET /v1/orders/stats?startDate=&endDate= (admin)."""

    def get(self, request):
        _require_admin(request)
        start, end = _period(request)
        return Response(analytics.order_stats(start, end))


class OrderForecastView(APIView):
    """GET /v1/orders/forecast?startDate=&endDate= : prévision sur des dates futures (admin)."""

    def get(self, request):
        _require_admin(request)
        start, end = _period(request)
        if (end - start).days > 92:
            raise ValidationError('Période limitée à 93 jours.')
        return Response(analytics.order_forecast(start, end, date.today()))
