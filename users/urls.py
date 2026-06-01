# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.UserLogin.as_view(), name="login"),
    path('logout/', views.logout_view, name="logout"),
    path('reset/', views.ResetPwd.as_view(), name="password_reset"),
    path('signup/', views.ResetPwd.as_view(), name="signup"),
    
    path('', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
]