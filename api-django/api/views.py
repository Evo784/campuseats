from datetime import date

import pandas as pd
from django.contrib.auth.hashers import check_password
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import make_token
from .models import Menu, Order, User
from .serializers import MenuSerializer, OrderSerializer


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        password = str(request.data.get('password', ''))
        user = User.objects.filter(email=email).select_related('role').first()
        # Même message dans les deux cas : on ne révèle pas si l'email existe
        if user is None or not check_password(password, user.password_hash):
            return Response({'detail': 'Email ou mot de passe incorrect.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        return Response({'token': make_token(user), 'id_user': user.id_user, 'role': user.role.label})


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


class MenuStatsView(APIView):
    """GET /v1/menus/stats?debut=YYYY-MM-DD&fin=YYYY-MM-DD : ventes par jour (admin seulement)."""

    def get(self, request):
        if not request.user.is_admin:
            raise PermissionDenied('Réservé à la cafétéria.')
        try:
            debut = date.fromisoformat(request.query_params['debut'])
            fin = date.fromisoformat(request.query_params['fin'])
        except (KeyError, ValueError):
            raise ValidationError('Paramètres debut et fin requis, format YYYY-MM-DD.')
        if debut > fin:
            raise ValidationError('debut doit être avant fin.')

        rows = list(Order.objects.filter(menu__menu_date__range=(debut, fin))
                    .values('menu__menu_date', 'menu__price', 'quantity'))
        if not rows:
            return Response({'debut': debut, 'fin': fin, 'total_quantity': 0,
                             'total_revenue': 0.0, 'days': []})

        df = pd.DataFrame(rows)
        df['revenue'] = df['menu__price'].astype(float) * df['quantity']
        per_day = (df.groupby('menu__menu_date')
                     .agg(quantity=('quantity', 'sum'), revenue=('revenue', 'sum'),
                          orders=('quantity', 'count'))
                     .reset_index().sort_values('menu__menu_date'))
        days = [{'menu_date': r.menu__menu_date, 'quantity': int(r.quantity),
                 'revenue': round(float(r.revenue), 2), 'orders': int(r.orders)}
                for r in per_day.itertuples()]
        return Response({'debut': debut, 'fin': fin,
                         'total_quantity': int(per_day['quantity'].sum()),
                         'total_revenue': round(float(per_day['revenue'].sum()), 2),
                         'days': days})
