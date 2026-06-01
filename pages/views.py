from django.shortcuts import render
from pages.forms import QuoteForm


def landing_page(request):
    return render(request, 'pages/landing_page.html')


def about_page(request):
    return render(request, 'pages/about.html')


def contact_form_view(request):
    """
    Renders the quote form. Submission is handled client-side:
    the JS in the template builds a WhatsApp deep-link and opens it.
    We still process the POST here so Django can render field-level
    validation errors if JavaScript is unavailable.
    """
    if request.method == 'POST':
        form = QuoteForm(request.POST)
        # If JS is disabled the form posts here; we re-render with errors.
        # If JS is enabled the submit event is intercepted before this runs.
    else:
        form = QuoteForm()

    return render(request, 'pages/contact_form.html', {'form': form})


def services_page(request):
    return render(request, 'pages/services.html')