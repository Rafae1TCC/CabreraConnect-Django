from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.urls import reverse_lazy
from django.shortcuts import redirect

# Create your views here.

class UserLogin(LoginView):
    template_name = "users/login.html"

    def get_success_url(self):
        return reverse_lazy("inv_list")

def logout_view(request):
    logout(request)
    return redirect('landing_page')

class ResetPwd(LoginView):
    template_name = "users/password_reset.html"

    def get_success_url(self):
        return reverse_lazy("home")

class UserSignup(LoginView):
    template_name = "users/signup.html"

    def get_success_url(self):
        return reverse_lazy("home")