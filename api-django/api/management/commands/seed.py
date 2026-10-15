"""Jeu de test : python manage.py seed

Crée (sans doublon, on peut le relancer) :
- 2 comptes de test, mots de passe hachés en Argon2id
- le menu d'exemple du 15/10/2026 (entrée, plat, dessert)

Réservé au développement : ne pas lancer en production.
"""
import datetime

from django.core.management.base import BaseCommand

from api.auth import hash_password
from api.models import Dish, Menu, MenuItem, Role, User

TEST_USERS = [
    ('etudiant@campus.fr', 'Etudiant123!', 'USER'),
    ('admin@campus.fr', 'Admin123!', 'ADMIN'),
]

EXAMPLE_MENU = (datetime.date(2026, 10, 15), '15.00', [
    ('Salad', 'STARTER'),
    ('Chicken', 'MAIN'),
    ('Chocolate Cake', 'DESSERT'),
])


class Command(BaseCommand):
    help = 'Crée les comptes de test (Argon2id) et le menu d\'exemple.'

    def handle(self, *args, **options):
        for email, password, role_label in TEST_USERS:
            role = Role.objects.get(label=role_label)
            # Le hash change à chaque appel (sel aléatoire) : on ne crée que si absent
            _, created = User.objects.get_or_create(
                email=email, defaults={'password_hash': hash_password(password), 'role': role})
            self.stdout.write(f"{'créé  ' if created else 'existe'} {role_label:5} {email}")

        day, price, dishes = EXAMPLE_MENU
        menu, created = Menu.objects.get_or_create(menu_date=day, defaults={'price': price})
        if created:
            for label, dish_type in dishes:
                dish = Dish.objects.create(label=label, type=dish_type)
                MenuItem.objects.create(menu=menu, dish=dish)
        self.stdout.write(f"{'créé  ' if created else 'existe'} menu du {day.isoformat()}")
