"""Modèles CampusEats. Les tables sont créées par les migrations Django (python manage.py migrate).

Les noms de tables et de colonnes suivent le schéma SQL de Nathan (docs/schema-nathan.sql).
"""
import datetime

from django.db import models
from django.db.models import Q
from django.db.models.functions import Length, Lower, Now


class Role(models.Model):
    id_role = models.BigAutoField(primary_key=True)
    label = models.CharField(unique=True, max_length=50)
    role_date = models.DateField(default=datetime.date.today)

    class Meta:
        db_table = 'roles'


class User(models.Model):
    id_user = models.BigAutoField(primary_key=True)
    email = models.CharField(unique=True, max_length=255)
    password_hash = models.TextField()  # Argon2id : "$argon2id$v=19$m=...$sel$hash"
    role = models.ForeignKey(Role, models.PROTECT, db_column='id_role')

    class Meta:
        db_table = 'users'
        indexes = [models.Index(fields=['role'], name='idx_users_role')]
        constraints = [
            models.CheckConstraint(
                condition=Q(email=Lower('email')) & Q(email__regex=r'^.+@.+\..+$'),
                name='ck_users_email'),
            models.CheckConstraint(condition=Q(password_hash__regex=r'.'), name='ck_users_password'),
        ]

    # Attributs attendus par DRF pour un "utilisateur" authentifié
    is_authenticated = True
    is_anonymous = False

    @property
    def is_admin(self):
        return self.role.label == 'ADMIN'


class Dish(models.Model):
    TYPES = ['STARTER', 'MAIN', 'DESSERT']

    id_dish = models.BigAutoField(primary_key=True)
    label = models.CharField(max_length=150)
    type = models.CharField(max_length=50)

    class Meta:
        db_table = 'dishes'
        constraints = [models.CheckConstraint(condition=Q(type__in=['STARTER', 'MAIN', 'DESSERT']),
                                              name='ck_dishes_type')]


class Menu(models.Model):
    """Un seul menu par jour (menu_date unique)."""
    id_menu = models.BigAutoField(primary_key=True)
    menu_date = models.DateField(unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'menus'
        constraints = [models.CheckConstraint(condition=Q(price__gte=0), name='ck_menus_price')]


class MenuItem(models.Model):
    """Table de liaison menus <-> plats."""
    pk = models.CompositePrimaryKey('menu', 'dish')
    menu = models.ForeignKey(Menu, models.CASCADE, db_column='id_menu', related_name='items')
    dish = models.ForeignKey(Dish, models.PROTECT, db_column='id_dish', related_name='items')

    class Meta:
        db_table = 'menu_items'
        indexes = [models.Index(fields=['dish'], name='idx_menu_items_dish')]


class Order(models.Model):
    """Une commande = le menu entier ; quantity = nombre de menus complets."""
    PAYMENT_METHODS = ['CARD', 'CASH', 'VISA', 'MASTERCARD', 'OTHER']

    id_order = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, models.PROTECT, db_column='id_user')
    menu = models.ForeignKey(Menu, models.PROTECT, db_column='id_menu')
    order_date = models.DateTimeField(db_default=Now())
    payment_method = models.CharField(max_length=20)
    is_delivered = models.BooleanField(default=False)
    quantity = models.IntegerField(default=1)

    class Meta:
        db_table = 'orders'
        indexes = [
            models.Index(fields=['user'], name='idx_orders_user'),
            models.Index(fields=['menu'], name='idx_orders_menu'),
            models.Index(fields=['order_date'], name='idx_orders_date'),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(payment_method__in=['CARD', 'CASH', 'VISA', 'MASTERCARD', 'OTHER']),
                                   name='ck_orders_payment'),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='ck_orders_quantity'),
        ]
