from django.urls import path
from . import views

urlpatterns = [

    path('login/', views.UserLogin.as_view(), name="login"),
    path('logout/', views.logout_view, name="logout"),
    path('reset/', views.ResetPwd.as_view(), name="password_reset"),
    path('signup/', views.ResetPwd.as_view(), name="signup"),

]