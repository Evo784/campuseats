from rest_framework import serializers

from .models import Dish, Menu, Order

TYPE_ORDER = {'STARTER': 0, 'MAIN': 1, 'DESSERT': 2}


class DishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dish
        fields = ['label', 'type']


class MenuSerializer(serializers.ModelSerializer):
    dishes = serializers.SerializerMethodField()

    class Meta:
        model = Menu
        fields = ['id_menu', 'menu_date', 'price', 'dishes']

    def get_dishes(self, menu):
        dishes = Dish.objects.filter(items__menu=menu)
        # Ordre garanti : entrée, plat, dessert
        dishes = sorted(dishes, key=lambda d: TYPE_ORDER.get(d.type, 99))
        return DishSerializer(dishes, many=True).data


class OrderSerializer(serializers.ModelSerializer):
    id_user = serializers.IntegerField(source='user_id', read_only=True)
    id_menu = serializers.PrimaryKeyRelatedField(source='menu', queryset=Menu.objects.all())
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_METHODS)
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = Order
        fields = ['id_order', 'id_user', 'id_menu', 'order_date', 'payment_method',
                  'is_delivered', 'quantity']
        read_only_fields = ['id_order', 'order_date', 'is_delivered']
