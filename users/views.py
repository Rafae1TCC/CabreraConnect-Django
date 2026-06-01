# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.models import User
from .forms import UserCreateForm, UserUpdateForm
from django.contrib.auth.forms import PasswordChangeForm

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

# Verificar si el usuario es superuser
def is_superuser(user):
    return user.is_superuser

# User List View
class UserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a esta página.")
        return redirect('inv_list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                models.Q(username__icontains=search) |
                models.Q(email__icontains=search) |
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search)
            )
        return queryset.order_by('-date_joined')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        users = context['users']
        
        # Calcular estadísticas directamente en Python
        context['search'] = self.request.GET.get('search', '')
        context['active_users_count'] = sum(1 for user in users if user.is_active)
        context['staff_count'] = sum(1 for user in users if user.is_staff)
        context['superuser_count'] = sum(1 for user in users if user.is_superuser)
        
        return context

# User Create View
class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_list')
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def form_valid(self, form):
        messages.success(self.request, f'Usuario {form.cleaned_data["username"]} creado exitosamente.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear Nuevo Usuario'
        context['button_text'] = 'Crear Usuario'
        return context

# User Update View
class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_list')
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def form_valid(self, form):
        messages.success(self.request, f'Usuario {form.cleaned_data["username"]} actualizado exitosamente.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Usuario'
        context['button_text'] = 'Actualizar Usuario'
        return context

# User Delete View
class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = User
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            messages.error(request, "No puedes eliminar tu propio usuario.")
            return redirect('user_list')
        messages.success(request, f'Usuario {user.username} eliminado exitosamente.')
        return super().delete(request, *args, **kwargs)

# Toggle user status (activate/deactivate)
@login_required
@user_passes_test(is_superuser)
def toggle_user_status(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        return JsonResponse({'error': 'No puedes cambiar tu propio estado'}, status=400)
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'activado' if user.is_active else 'desactivado'
    return JsonResponse({'success': True, 'message': f'Usuario {status} exitosamente', 'is_active': user.is_active})