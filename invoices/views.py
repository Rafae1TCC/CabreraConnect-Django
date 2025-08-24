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

def inv_list(request):
    invoices = Invoice.objects.all().order_by('-date')
    return render(request, 'invoices/inv_list.html', {'invoices': invoices})

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
            invoice = form.save(commit=False)
            
            # Process products from the form
            products_json = request.POST.get('products', '[]')
            try:
                products_data = json.loads(products_json)
                for product in products_data:
                    invoice.add_product(product)
            except json.JSONDecodeError:
                pass
            
            invoice.save()
            # Redirect to the invoice template with download parameter
            return redirect(f'{reverse("inv_template")}?id={invoice.id}&download=true')
    
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
                updated_invoice = form.save(commit=False)
                
                # Update products if provided
                products_json = request.POST.get('products')
                if products_json:
                    try:
                        updated_invoice.products = json.loads(products_json)
                    except json.JSONDecodeError:
                        pass
                
                updated_invoice.save()
                # Redirect to the invoice template with download parameter
                return redirect(f'{reverse("inv_template")}?id={updated_invoice.id}&download=true')
    
    form = InvoiceForm(instance=invoice)
    return render(request, 'invoices/inv_edit.html', {
        'form': form,
        'invoice': invoice,
        'products_json': json.dumps(invoice.products),
        'default_tax_rate': Invoice._meta.get_field('tax_rate').default
    })

def inv_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        invoice.delete()
        return redirect('inv_list')
    return render(request, 'invoices/inv_delete.html', {'invoice': invoice})

def invoice_template(request):
    invoice_id = request.GET.get('id')
    if not invoice_id:
        return redirect('inv_list')

    invoice = get_object_or_404(Invoice, id=invoice_id)

    products = invoice.products or []
    pages = []

    # Primera página con 11 productos
    first_page_count = 11
    pages.append(products[:first_page_count])

    # El resto con 18 productos por página
    remaining = products[first_page_count:]
    subsequent_page_count = 18
    for i in range(0, len(remaining), subsequent_page_count):
        pages.append(remaining[i:i + subsequent_page_count])

    return render(request, 'invoices/inv_template.html', {
        'invoice': invoice,
        'preview': True,
        'pages': pages,
        'total_pages': len(pages) or 1,
    })


def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    products = invoice.products or []
    pages = []

    # Primera página con 11 productos
    first_page_count = 11
    pages.append(products[:first_page_count])

    # El resto con 18 productos por página
    remaining = products[first_page_count:]
    subsequent_page_count = 18
    for i in range(0, len(remaining), subsequent_page_count):
        pages.append(remaining[i:i + subsequent_page_count])

    html_string = render_to_string("invoices/inv_template.html", {
        "invoice": invoice,
        "preview": False,
        "pages": pages,
        "total_pages": len(pages) or 1,
    })

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.folio}.pdf"'

    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response