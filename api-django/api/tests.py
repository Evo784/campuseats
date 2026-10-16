import time
from datetime import date

import jwt
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from . import analytics
from .auth import ALGORITHM, hash_password, verify_password
from .models import Dish, Menu, MenuItem, Order, Role, User

PASSWORD = 'Motdepasse1!'


def make_user(email, role='USER'):
    return User.objects.create(email=email, password_hash=hash_password(PASSWORD),
                               role=Role.objects.get(label=role))


def make_menu(day, price=15):
    menu = Menu.objects.create(menu_date=day, price=price)
    for label, type_ in [('Cake', 'DESSERT'), ('Salad', 'STARTER'), ('Chicken', 'MAIN')]:
        MenuItem.objects.create(menu=menu, dish=Dish.objects.create(label=label, type=type_))
    return menu


class ApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_user('etu@campus.fr')
        self.admin = make_user('admin@campus.fr', 'ADMIN')

    def login(self, email):
        r = self.client.post('/v1/login', {'email': email, 'password': PASSWORD}, format='json')
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + r.json()['token'])


class PasswordTests(TestCase):
    def test_hash_is_argon2id_and_verifies(self):
        hashed = hash_password(PASSWORD)
        self.assertTrue(hashed.startswith('$argon2id$'))
        self.assertTrue(verify_password(hashed, PASSWORD))
        self.assertFalse(verify_password(hashed, 'autre'))
        self.assertFalse(verify_password('pas un hash', PASSWORD))


class UserAndLoginTests(ApiTestCase):
    def test_create_user_is_always_a_student(self):
        r = self.client.post('/v1/users', {'email': 'New@Campus.fr', 'password': PASSWORD,
                                           'role': 'ADMIN'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['role'], 'USER')
        user = User.objects.get(email='new@campus.fr')
        self.assertTrue(user.password_hash.startswith('$argon2id$'))

    def test_create_user_errors(self):
        post = lambda body: self.client.post('/v1/users', body, format='json').status_code
        self.assertEqual(post({'email': 'etu@campus.fr', 'password': PASSWORD}), 409)
        self.assertEqual(post({'email': 'pas-un-email', 'password': PASSWORD}), 400)
        self.assertEqual(post({'email': 'a@b.fr', 'password': 'court'}), 400)

    def test_login_returns_jwt(self):
        r = self.client.post('/v1/login', {'email': 'etu@campus.fr', 'password': PASSWORD}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['expires_in'], 1800)
        payload = jwt.decode(r.json()['token'], settings.SECRET_KEY, algorithms=[ALGORITHM])
        self.assertEqual(payload['sub'], str(self.student.id_user))
        self.assertEqual(payload['exp'] - payload['iat'], 1800)

    def test_login_wrong_credentials(self):
        for body in [{'email': 'etu@campus.fr', 'password': 'faux'},
                     {'email': 'inconnu@campus.fr', 'password': PASSWORD}, {}]:
            r = self.client.post('/v1/login', body, format='json')
            self.assertEqual(r.status_code, 401)
            self.assertNotIn('token', r.json())

    def test_protected_route_rejects_missing_bad_and_expired_token(self):
        url = '/v1/dishes/stats?startDate=2026-10-01&endDate=2026-10-15'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer abc')
        self.assertEqual(self.client.get(url).status_code, 401)
        now = int(time.time())
        expired = jwt.encode({'sub': str(self.student.id_user), 'iat': now - 3600, 'exp': now - 1800},
                             settings.SECRET_KEY, algorithm=ALGORITHM)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + expired)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 401)
        self.assertIn('expiré', r.json()['detail'])

    def test_token_signed_with_another_key_is_rejected(self):
        forged = jwt.encode({'sub': str(self.admin.id_user), 'exp': int(time.time()) + 600},
                            'autre-cle-secrete-de-plus-de-32-caracteres!', algorithm=ALGORITHM)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + forged)
        self.assertEqual(self.client.get('/v1/dishes/stats?startDate=2026-10-01&endDate=2026-10-02')
                         .status_code, 401)


class MenuTests(ApiTestCase):
    def test_menu_by_date_and_id_with_ordered_dishes(self):
        menu = make_menu(date(2026, 10, 15))
        for url in ['/v1/menus?date=2026-10-15', f'/v1/menus/{menu.id_menu}']:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertEqual([d['type'] for d in r.json()['dishes']], ['STARTER', 'MAIN', 'DESSERT'])
            self.assertEqual(r.json()['price'], 15.0)

    def test_menu_errors(self):
        self.assertEqual(self.client.get('/v1/menus?date=2026-10-15').status_code, 404)
        self.assertEqual(self.client.get('/v1/menus?date=nimporte').status_code, 400)
        self.assertEqual(self.client.get('/v1/menus/999').status_code, 404)


class OrderTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.menu = make_menu(date(2026, 10, 15))

    def create_order(self, **extra):
        body = {'id_menu': self.menu.id_menu, 'quantity': 2, 'payment_method': 'VISA', **extra}
        return self.client.post('/v1/orders', body, format='json')

    def test_create_order_uses_user_from_token(self):
        self.login('etu@campus.fr')
        r = self.create_order(id_user=self.admin.id_user)  # ignoré
        self.assertEqual(r.status_code, 201)
        data = r.json()
        self.assertEqual(data['id_user'], self.student.id_user)
        self.assertEqual(data['total_price'], 30.0)
        self.assertFalse(data['is_delivered'])
        self.assertEqual([d['label'] for d in data['dishes']], ['Salad', 'Chicken', 'Cake'])

    def test_create_order_requires_login(self):
        self.assertEqual(self.create_order().status_code, 401)

    def test_create_order_validation(self):
        self.login('etu@campus.fr')
        self.assertEqual(self.create_order(quantity=0).status_code, 400)
        self.assertEqual(self.create_order(payment_method='BITCOIN').status_code, 400)
        self.assertEqual(self.create_order(id_menu=999).status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_only_owner_or_admin_can_read(self):
        self.login('etu@campus.fr')
        order_id = self.create_order().json()['id_order']
        self.assertEqual(self.client.get(f'/v1/orders/{order_id}').status_code, 200)
        make_user('autre@campus.fr')
        self.login('autre@campus.fr')
        self.assertEqual(self.client.get(f'/v1/orders/{order_id}').status_code, 403)
        self.login('admin@campus.fr')
        self.assertEqual(self.client.get(f'/v1/orders/{order_id}').status_code, 200)
        self.assertEqual(self.client.get('/v1/orders/999').status_code, 404)

    def test_patch_delivered_is_admin_only(self):
        self.login('etu@campus.fr')
        order_id = self.create_order().json()['id_order']
        patch = lambda body: self.client.patch(f'/v1/orders/{order_id}', body, format='json')
        self.assertEqual(patch({'is_delivered': True}).status_code, 403)
        self.login('admin@campus.fr')
        r = patch({'is_delivered': True})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['is_delivered'])
        self.assertTrue(Order.objects.get(pk=order_id).is_delivered)
        self.assertEqual(patch({'is_delivered': 'oui'}).status_code, 400)


class StatsTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        # 10/10 : 2 menus, 11/10 : 6 menus, 12/10 : aucune commande, 13/10 : 8 menus
        self.menus = {d: make_menu(date(2026, 10, d), price=12) for d in (10, 11, 12, 13)}
        for day, qty, pay, done in [(10, 2, 'VISA', True), (11, 6, 'CASH', False),
                                    (13, 5, 'VISA', False), (13, 3, 'CASH', True)]:
            Order.objects.create(user=self.student, menu=self.menus[day], quantity=qty,
                                 payment_method=pay, is_delivered=done)
        self.period = 'startDate=2026-10-10&endDate=2026-10-13'

    def test_dish_stats_for_any_logged_user(self):
        self.login('etu@campus.fr')
        r = self.client.get(f'/v1/dishes/stats?{self.period}')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual((data['total_orders'], data['total_quantity']), (4, 16))
        self.assertEqual([(d['type'], d['quantity']) for d in data['dishes']],
                         [('STARTER', 16), ('MAIN', 16), ('DESSERT', 16)])

    def test_dish_stats_period_filter_and_empty(self):
        self.login('etu@campus.fr')
        data = self.client.get('/v1/dishes/stats?startDate=2026-10-11&endDate=2026-10-11').json()
        self.assertEqual((data['total_orders'], data['total_quantity']), (1, 6))
        data = self.client.get('/v1/dishes/stats?startDate=2020-01-01&endDate=2020-01-31').json()
        self.assertEqual((data['total_orders'], data['dishes']), (0, []))

    def test_order_stats(self):
        self.login('admin@campus.fr')
        data = self.client.get(f'/v1/orders/stats?{self.period}').json()
        self.assertEqual(data['total_orders'], 4)
        self.assertEqual(data['total_quantity'], 16)
        self.assertEqual(data['total_revenue'], 192.0)
        self.assertEqual(data['average_order_value'], 48.0)
        self.assertEqual((data['delivered_orders'], data['pending_orders']), (2, 2))
        self.assertEqual(data['payment_methods'], [{'method': 'CASH', 'count': 2},
                                                   {'method': 'VISA', 'count': 2}])

    def test_order_stats_empty_period(self):
        self.login('admin@campus.fr')
        data = self.client.get('/v1/orders/stats?startDate=2020-01-01&endDate=2020-01-31').json()
        self.assertEqual((data['total_orders'], data['total_revenue'], data['payment_methods']),
                         (0, 0.0, []))

    def test_admin_routes_forbidden_for_student(self):
        self.login('etu@campus.fr')
        self.assertEqual(self.client.get(f'/v1/orders/stats?{self.period}').status_code, 403)
        self.assertEqual(self.client.get(f'/v1/orders/forecast?{self.period}').status_code, 403)

    def test_period_validation(self):
        self.login('admin@campus.fr')
        for query in ['', 'startDate=2026-10-10', 'startDate=nimporte&endDate=2026-10-13',
                      'startDate=2026-10-13&endDate=2026-10-10']:
            for route in ['dishes/stats', 'orders/stats', 'orders/forecast']:
                self.assertEqual(self.client.get(f'/v1/{route}?{query}').status_code, 400,
                                 f'{route}?{query}')
        self.assertEqual(self.client.get('/v1/orders/forecast?startDate=2026-11-01&endDate=2027-03-01')
                         .status_code, 400)

    def test_forecast_values(self):
        # Mardi 13/10/2026 : 8 menus. Lundi 12 : 0. Dimanche 11 : 6. Samedi 10 : 2.
        # Prévision d'un mardi futur = moyenne des mardis passés = 8, prix 12 € => 96 €.
        result = analytics.order_forecast(date(2026, 10, 20), date(2026, 10, 20), today=date(2026, 10, 14))
        day = result['daily_forecast'][0]
        self.assertEqual(day, {'date': date(2026, 10, 20), 'predicted_orders': 2,
                               'predicted_quantity': 8, 'predicted_revenue': 96.0})
        self.assertEqual(result['forecast'], {'total_orders': 2, 'total_quantity': 8,
                                              'total_revenue': 96.0})

    def test_forecast_unknown_weekday_falls_back_to_overall_mean(self):
        # Jeudi : aucun jeudi dans l'historique => moyenne des 4 jours = (2+6+0+8)/4 = 4
        result = analytics.order_forecast(date(2026, 10, 15), date(2026, 10, 15), today=date(2026, 10, 14))
        self.assertEqual(result['daily_forecast'][0]['predicted_quantity'], 4)

    def test_forecast_without_history(self):
        result = analytics.order_forecast(date(2026, 10, 15), date(2026, 10, 16), today=date(2020, 1, 1))
        self.assertEqual(result['daily_forecast'], [])
        self.assertEqual(result['forecast']['total_quantity'], 0)

    def test_forecast_route_shape(self):
        self.login('admin@campus.fr')
        r = self.client.get('/v1/orders/forecast?startDate=2026-10-16&endDate=2026-10-18')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {'startDate', 'endDate', 'based_on_days', 'forecast',
                                         'daily_forecast'})
