from django.urls import path

from . import views

urlpatterns = [
    path('users', views.UserCreateView.as_view()),
    path('login', views.LoginView.as_view()),
    path('menus', views.MenuListView.as_view()),
    path('menus/<int:id_menu>', views.MenuByIdView.as_view()),
    path('dishes/stats', views.DishStatsView.as_view()),
    path('orders/stats', views.OrderStatsView.as_view()),
    path('orders/forecast', views.OrderForecastView.as_view()),
    path('orders', views.OrderCreateView.as_view()),
    path('orders/<int:id_order>', views.OrderDetailView.as_view()),
]
