from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.inv_list, name="inv_list"),
    path('create/', views.inv_crt, name="inv_crt"),
    path('edit/<int:pk>/', views.inv_edit, name="inv_edit"),
]