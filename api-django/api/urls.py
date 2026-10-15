from django.urls import path

from . import views

urlpatterns = [
    path('login', views.LoginView.as_view()),
    path('menus', views.MenuListView.as_view()),
    path('menus/stats', views.MenuStatsView.as_view()),
    path('menus/<int:id_menu>', views.MenuByIdView.as_view()),
    path('orders', views.OrderCreateView.as_view()),
    path('orders/<int:id_order>', views.OrderDetailView.as_view()),
]
