from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import Invoice
from .forms import InvoiceForm  # You'll need to update your form as well
from django.urls import reverse 
import json
from decimal import Decimal
from django.template.loader import render_to_string
from django.http import HttpResponse
from weasyprint import HTML, CSS
import tempfile
from django.core.mail import EmailMessage
import io
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

class InvoiceRenderer:
    """Helper class to handle invoice rendering logic"""
    
    def __init__(self, invoice):
        self.invoice = invoice

    def get_pages_data(self):
        """Calculate pagination for invoice products"""
        products = self.invoice.products or []
        pages = []

        # First page with 11 products
        first_page_count = 11
        pages.append(products[:first_page_count])

        # Rest of the pages with 19 products
        remaining = products[first_page_count:]
        subsequent_page_count = 19
        for i in range(0, len(remaining), subsequent_page_count):
            pages.append(remaining[i:i + subsequent_page_count])

        return {
            'pages': pages,
            'total_pages': len(pages) or 1
        }

    def get_context(self, preview=True):
        """Get template context for invoice rendering"""
        pages_data = self.get_pages_data()
        return {
            'invoice': self.invoice,
            'preview': preview,
            'pages': pages_data['pages'],
            'total_pages': pages_data['total_pages'],
        }

    def render_pdf(self, request, preview=False):
        """Generate PDF from invoice template and return as bytes"""
        html_string = render_to_string(
            "invoices/inv_template.html",
            self.get_context(preview=preview)
        )
        pdf_io = io.BytesIO()
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(pdf_io)
        return pdf_io.getvalue()
    

def invoice_template(request):
    invoice_id = request.GET.get('id')
    if not invoice_id:
        return redirect('inv_list')

    invoice = get_object_or_404(Invoice, id=invoice_id)
    renderer = InvoiceRenderer(invoice)
    
    return render(request, 'invoices/inv_template.html', renderer.get_context(preview=True))


def invoice_pdf(request, pk):
    """Download PDF invoice"""
    invoice = get_object_or_404(Invoice, pk=pk)
    renderer = InvoiceRenderer(invoice)
    pdf_bytes = renderer.render_pdf(request, preview=False)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.folio}.pdf"'
    return response


def invoice_email(request, pk):
    """Send PDF invoice to client and seller via email"""
    invoice = get_object_or_404(Invoice, pk=pk)
    renderer = InvoiceRenderer(invoice)
    pdf_bytes = renderer.render_pdf(request, preview=False)

    subject = f"Factura {invoice.folio} - Cabrera Connect"
    body = (
        f"Estimado {invoice.clt_name},\n\n"
        f"Adjuntamos la factura correspondiente a su compra.\n\n"
        f"Gracias por su preferencia.\n"
        f"Atentamente,\nCabrera Connect"
    )

    recipients = []
    if invoice.clt_email:
        recipients.append(invoice.clt_email)
    if invoice.sell_email:
        recipients.append(invoice.sell_email)

    if not recipients:
        messages.error(request, "No hay correos configurados para enviar esta factura.")
        return redirect("inv_template")  # redirige a preview

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email="noreply@cabreraconnect.com",
        to=recipients,
    )
    email.attach(f"invoice_{invoice.folio}.pdf", pdf_bytes, "application/pdf")

    try:
        email.send()
        messages.success(
            request,
            f"Factura enviada correctamente a: {', '.join(recipients)}"
        )
    except Exception as e:
        messages.error(request, f"Error al enviar el correo: {e}")

    # Redirige al preview con mensaje
    return redirect(f"/invoices/template?id={invoice.id}")

def inv_list(request):
    # --- Filtros ---
    search_id = request.GET.get("id", "").strip()
    search_title = request.GET.get("title", "").strip()
    search_date = request.GET.get("date", "").strip()
    search_client = request.GET.get("client", "").strip()
    search_seller = request.GET.get("seller", "").strip()

    # --- Ordenamiento ---
    sort = request.GET.get("sort", "date")  # default: date
    direction = request.GET.get("direction", "desc")

    # Map de campos permitidos
    sort_fields = {
        "id": "id",
        "title": "title",
        "date": "date",
        "amount": "total",
        "client": "clt_name",
        "seller": "sell_name",
    }

    sort_field = sort_fields.get(sort, "date")
    if direction == "desc":
        sort_field = "-" + sort_field

    invoices = Invoice.objects.all().order_by(sort_field)

    # --- Filtros aplicados ---
    if search_id:
        invoices = invoices.filter(id__icontains=search_id)
    if search_title:
        invoices = invoices.filter(title__icontains=search_title)
    if search_date:
        invoices = invoices.filter(date=search_date)
    if search_client:
        invoices = invoices.filter(clt_name__icontains=search_client)
    if search_seller:
        invoices = invoices.filter(sell_name__icontains=search_seller)

    # --- Fix invalid totals ---
    for invoice in invoices:
        if invoice.total is None or isinstance(invoice.total, str):
            try:
                invoice.calculate_totals()
                invoice.save()
            except:
                invoice.subtotal = Decimal("0.00")
                invoice.total_discount = Decimal("0.00")
                invoice.total_tax = Decimal("0.00")
                invoice.total = Decimal("0.00")
                invoice.save()

    # --- Paginación ---
    per_page = request.GET.get("per_page", 15)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 15

    paginator = Paginator(invoices, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "invoices": page_obj,
        "page_obj": page_obj,
        "per_page": per_page,
        "per_page_options": [15, 25, 50, 100],
        "search_params": {
            "id": search_id,
            "title": search_title,
            "date": search_date,
            "client": search_client,
            "seller": search_seller,
        },
        "sort": sort,
        "direction": direction,
    }
    return render(request, "invoices/inv_list.html", context)


def inv_crt(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'POST':
        # Handle AJAX request for adding products
        try:
            data = json.loads(request.body)
            product_data = {
                'name': data.get('name', ''),
                'price': Decimal(data.get('price', 0)),
                'quantity': int(data.get('quantity', 1)),
                'discount_percent': Decimal(data.get('discount_percent', 0)),
            }
            return JsonResponse({'success': True, 'product': product_data})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save()  # Let the form handle products via products_json
            return redirect(f'{reverse("inv_template")}?id={invoice.id}&download=true')
        else:
            # Debug: print form errors
            print("Form errors:", form.errors)
    
    form = InvoiceForm()
    return render(request, 'invoices/inv_crt.html', {
        'form': form,
        'default_tax_rate': Invoice._meta.get_field('tax_rate').default
    })


def inv_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'POST':
        # Handle AJAX product updates
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'add_product':
                product_data = {
                    'name': data.get('name', ''),
                    'price': Decimal(data.get('price', 0)),
                    'quantity': int(data.get('quantity', 1)),
                    'discount_percent': Decimal(data.get('discount_percent', 0)),
                }
                invoice.add_product(product_data)
                invoice.save()
                return JsonResponse({'success': True, 'products': invoice.products})
            
            elif action == 'remove_product':
                index = int(data.get('index', -1))
                if 0 <= index < len(invoice.products):
                    invoice.products.pop(index)
                    invoice.save()
                    return JsonResponse({'success': True, 'products': invoice.products})
                return JsonResponse({'success': False, 'error': 'Invalid index'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            # Use the form's save method which handles products via products_json
            updated_invoice = form.save()
            # Redirect to the invoice template with download parameter
            return redirect(f'{reverse("inv_template")}?id={updated_invoice.id}&download=true')
        else:
            # Form is invalid, but we want to preserve the data
            print("Form errors:", form.errors)
            # Continue to render the form with errors
    
    # For GET requests or invalid POST, show the form with current data
    form = InvoiceForm(instance=invoice)
    return render(request, 'invoices/inv_edit.html', {
        'form': form,
        'invoice': invoice,
        'default_tax_rate': Invoice._meta.get_field('tax_rate').default
    })


def inv_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        invoice.delete()
        return redirect('inv_list')
    return render(request, 'invoices/inv_delete.html', {'invoice': invoice})

