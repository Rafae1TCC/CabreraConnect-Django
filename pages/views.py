from django.shortcuts import render

# Create your views here.

def landing_page(request):
    return render(request, 'pages/landing_page.html')
def about_page(request):
    return render(request, 'pages/about.html')
def contact_page(request):
    return render(request, 'pages/contact.html')
def services_page(request):
    return render(request, 'pages/services.html')
