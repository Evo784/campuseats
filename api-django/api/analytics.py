"""Statistiques et prévisions (pandas)."""
from datetime import timedelta

import pandas as pd

from .models import Dish, Menu, Order

TYPE_ORDER = {'STARTER': 0, 'MAIN': 1, 'DESSERT': 2}
HISTORY_DAYS = 28  # historique utilisé pour la prévision


def _money(value):
    return round(float(value), 2)


def dish_stats(start, end):
    """Quantité commandée par plat entre deux dates (un menu commandé x fois = chaque plat x fois)."""
    orders = Order.objects.filter(menu__menu_date__range=(start, end))
    total_orders = orders.count()
    rows = list(Order.objects.filter(menu__menu_date__range=(start, end))
                .values('quantity', 'menu__items__dish__label', 'menu__items__dish__type'))
    rows = [r for r in rows if r['menu__items__dish__label'] is not None]
    dishes = []
    if rows:
        df = pd.DataFrame(rows)
        grouped = (df.groupby(['menu__items__dish__label', 'menu__items__dish__type'])['quantity']
                     .sum().reset_index())
        grouped['rank'] = grouped['menu__items__dish__type'].map(TYPE_ORDER)
        grouped = grouped.sort_values(['rank', 'quantity'], ascending=[True, False])
        dishes = [{'label': r.menu__items__dish__label, 'type': r.menu__items__dish__type,
                   'quantity': int(r.quantity)} for r in grouped.itertuples()]
    total_quantity = sum(o['quantity'] for o in orders.values('quantity'))
    return {'startDate': start, 'endDate': end, 'total_orders': total_orders,
            'total_quantity': total_quantity, 'dishes': dishes}


def order_stats(start, end):
    """Résumé des commandes entre deux dates."""
    rows = list(Order.objects.filter(menu__menu_date__range=(start, end))
                .values('menu__price', 'quantity', 'payment_method', 'is_delivered'))
    result = {'startDate': start, 'endDate': end, 'total_orders': 0, 'total_quantity': 0,
              'total_revenue': 0.0, 'average_order_value': 0.0, 'delivered_orders': 0,
              'pending_orders': 0, 'payment_methods': []}
    if not rows:
        return result

    df = pd.DataFrame(rows)
    df['revenue'] = df['menu__price'].astype(float) * df['quantity']
    delivered = int(df['is_delivered'].sum())
    # Tri stable : plus utilisé d'abord, puis ordre alphabétique
    methods = (df.groupby('payment_method').size().reset_index(name='count')
                 .sort_values(['count', 'payment_method'], ascending=[False, True]))
    result.update({
        'total_orders': len(df),
        'total_quantity': int(df['quantity'].sum()),
        'total_revenue': _money(df['revenue'].sum()),
        'average_order_value': _money(df['revenue'].mean()),
        'delivered_orders': delivered,
        'pending_orders': len(df) - delivered,
        'payment_methods': [{'method': r.payment_method, 'count': int(r.count)} for r in methods.itertuples()],
    })
    return result


def order_forecast(start, end, today):
    """Prévision jour par jour entre start et end.

    Pour chaque date : moyenne des jours de menu de même jour de semaine sur les
    HISTORY_DAYS derniers jours (sinon moyenne de tous les jours). Un jour avec menu
    mais sans commande compte pour 0. Le CA prévu = quantité prévue x prix moyen du menu.
    """
    since = today - timedelta(days=HISTORY_DAYS)
    menus = {m.id_menu: m for m in Menu.objects.filter(menu_date__gt=since, menu_date__lte=today)}
    orders = list(Order.objects.filter(menu_id__in=menus).values('menu_id', 'quantity'))
    if not menus:
        return {'startDate': start, 'endDate': end, 'based_on_days': 0,
                'forecast': {'total_orders': 0, 'total_quantity': 0, 'total_revenue': 0.0},
                'daily_forecast': []}

    daily = pd.DataFrame({'menu_id': list(menus),
                          'date': [pd.Timestamp(m.menu_date) for m in menus.values()],
                          'price': [float(m.price) for m in menus.values()]})
    if orders:
        o = pd.DataFrame(orders).groupby('menu_id').agg(
            predicted_orders=('quantity', 'size'), predicted_quantity=('quantity', 'sum'))
        daily = daily.join(o, on='menu_id')
    else:
        daily['predicted_orders'] = 0
        daily['predicted_quantity'] = 0
    daily = daily.fillna({'predicted_orders': 0, 'predicted_quantity': 0})
    daily['weekday'] = daily['date'].dt.weekday
    overall = daily[['predicted_orders', 'predicted_quantity']].mean()
    by_weekday = daily.groupby('weekday')[['predicted_orders', 'predicted_quantity']].mean()
    price = float(daily['price'].mean())

    days = []
    day = start
    while day <= end:
        src = by_weekday.loc[day.weekday()] if day.weekday() in by_weekday.index else overall
        orders_n, qty = round(float(src['predicted_orders'])), round(float(src['predicted_quantity']))
        days.append({'date': day, 'predicted_orders': orders_n, 'predicted_quantity': qty,
                     'predicted_revenue': _money(qty * price)})
        day += timedelta(days=1)

    return {
        'startDate': start,
        'endDate': end,
        'based_on_days': len(daily),
        'forecast': {'total_orders': sum(d['predicted_orders'] for d in days),
                     'total_quantity': sum(d['predicted_quantity'] for d in days),
                     'total_revenue': _money(sum(d['predicted_revenue'] for d in days))},
        'daily_forecast': days,
    }
