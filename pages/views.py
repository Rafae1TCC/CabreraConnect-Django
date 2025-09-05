from django.shortcuts import render
from pages.forms import ContactForm
from django.core.mail import send_mail

# Create your views here.

def landing_page(request):
    return render(request, 'pages/landing_page.html')
def about_page(request):
    return render(request, 'pages/about.html')
def contact_form_view(request):
    form = ContactForm()
    
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']

            message_body = (
                f"You have a new email from your portfolio page \n"
                f"Name: {name}\n"
                f"Email: {email}\n"
                f"Message: {message}"
            )

            try:
                send_mail(
                    "Email from Portfolio",
                    message_body,
                    email,  # From email
                    ['rafael231927@gmail.com'],  # To email (your inbox)
                )
                return render(request, 'pages/contact_form.html', {
                    'form': ContactForm(),  # Reset form on success
                    'success': True,
                })
            except Exception as e:
                print(f"Error sending email: {e}")
                return render(request, 'pages/contact_form.html', {
                    'form': form,  # Keep submitted data on error
                    'error': True,
                })

    # Return response for GET requests (or invalid POST)
    return render(request, 'pages/contact_form.html', {'form': form})
def services_page(request):
    return render(request, 'pages/services.html')
