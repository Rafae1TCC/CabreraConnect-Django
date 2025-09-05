from django.urls import path
from pages import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('about/', views.about_page, name='about'),
    path('contact/', views.contact_form_view, name = 'contact_form'),
    path('services/', views.services_page, name='services'),
]