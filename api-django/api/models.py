"""Modèles mappés sur les tables PostgreSQL créées par db/init/01-schema.sql.

managed = False : Django ne crée ni ne modifie ces tables, le schéma SQL fait foi.
"""
from django.db import models
from django.utils import timezone


class Role(models.Model):
    id_role = models.BigAutoField(primary_key=True)
    label = models.CharField(unique=True, max_length=50)
    role_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'roles'


class User(models.Model):
    id_user = models.BigAutoField(primary_key=True)
    email = models.CharField(unique=True, max_length=255)
    password_hash = models.TextField()
    role = models.ForeignKey(Role, models.DO_NOTHING, db_column='id_role')

    class Meta:
        managed = False
        db_table = 'users'

    # Attributs attendus par DRF pour un "utilisateur" authentifié
    is_authenticated = True
    is_anonymous = False

    @property
    def is_admin(self):
        return self.role.label == 'ADMIN'


class Dish(models.Model):
    id_dish = models.BigAutoField(primary_key=True)
    label = models.CharField(max_length=150)
    type = models.CharField(max_length=50)  # STARTER | MAIN | DESSERT

    class Meta:
        managed = False
        db_table = 'dishes'


class Menu(models.Model):
    id_menu = models.BigAutoField(primary_key=True)
    menu_date = models.DateField(unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'menus'


class MenuItem(models.Model):
    pk = models.CompositePrimaryKey('menu', 'dish')
    menu = models.ForeignKey(Menu, models.DO_NOTHING, db_column='id_menu', related_name='items')
    dish = models.ForeignKey(Dish, models.DO_NOTHING, db_column='id_dish', related_name='items')

    class Meta:
        managed = False
        db_table = 'menu_items'


class Order(models.Model):
    PAYMENT_METHODS = ['CARD', 'CASH', 'VISA', 'MASTERCARD', 'OTHER']

    id_order = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, models.DO_NOTHING, db_column='id_user')
    menu = models.ForeignKey(Menu, models.DO_NOTHING, db_column='id_menu')
    order_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=20)
    is_delivered = models.BooleanField(default=False)
    quantity = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'orders'
