from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.inv_list, name="inv_list"),
    path('create/', views.inv_crt, name="inv_crt"),
    path('edit/<int:pk>/', views.inv_edit, name="inv_edit"),
    path('delete/<int:pk>/', views.inv_delete, name="inv_delete"),
    path('template/', views.invoice_template, name="inv_template"),
    path('pdf/<int:pk>/', views.invoice_pdf, name="inv_pdf"),
    path('send-email/<int:pk>/', views.invoice_email, name="inv_email"),
]