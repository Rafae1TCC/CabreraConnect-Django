from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import Invoice
from .forms import InvoiceForm  # You'll need to update your form as well
import json
from decimal import Decimal

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
                'description': data.get('description', ''),
                'price': Decimal(data.get('price', 0)),
                'quantity': int(data.get('quantity', 1)),
                'discount_percent': Decimal(data.get('discount_percent', 0)),
                'taxable': data.get('taxable', True),
                'sku': data.get('sku', ''),
                'warranty_months': int(data.get('warranty_months', 0))
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
            return redirect('inv_list')
    
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
            return redirect('inv_list')
    
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