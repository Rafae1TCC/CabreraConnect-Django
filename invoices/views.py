from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import Invoice
from .forms import InvoiceForm
from django.urls import reverse
import json
from decimal import Decimal
from django.template.loader import render_to_string
from django.http import HttpResponse
from weasyprint import HTML
import io
from django.core.mail import EmailMessage
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth, TruncDay, TruncYear
import base64
import os
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from calendar import month_name



# ── Audit helpers ─────────────────────────────────────────────────────────────

def _get_actor(request):
    """Return a display name for whoever is making the request."""
    if request.user and request.user.is_authenticated:
        return request.user.get_full_name() or request.user.username
    return "Unknown user"


def _snapshot_fields(invoice):
    """
    Plain-dict snapshot of every auditable field on an invoice.
    Called before and after a save so we can diff them.
    """
    return {
        "title":          invoice.title,
        "date":           str(invoice.date) if invoice.date else None,
        "folio":          invoice.folio,
        "clt_name":       invoice.clt_name,
        "clt_email":      invoice.clt_email,
        "sell_name":      invoice.sell_name,
        "sell_email":     invoice.sell_email,
        "currency":       invoice.currency,
        "payment_method": invoice.payment_method,
        "tax_rate":       str(invoice.tax_rate),
        "comments":       invoice.comments or "",
        "subtotal":       str(invoice.subtotal),
        "total_discount": str(invoice.total_discount),
        "total_tax":      str(invoice.total_tax),
        "total":          str(invoice.total),
        "products":       invoice.products or [],
    }


FIELD_LABELS = {
    "title":          "Title",
    "date":           "Date",
    "folio":          "Folio",
    "clt_name":       "Client Name",
    "clt_email":      "Client Email",
    "sell_name":      "Seller Name",
    "sell_email":     "Seller Email",
    "currency":       "Currency",
    "payment_method": "Payment Method",
    "tax_rate":       "Tax Rate",
    "comments":       "Comments",
    "subtotal":       "Subtotal",
    "total_discount": "Total Discount",
    "total_tax":      "Tax Amount",
    "total":          "Total Amount",
}


def _diff_snapshots(before, after):
    """
    Return a list of change dicts  { field, from, to }
    by comparing two _snapshot_fields() results.
    """
    changes = []

    for key, label in FIELD_LABELS.items():
        old_val = str(before.get(key) or "")
        new_val = str(after.get(key) or "")
        if old_val != new_val:
            changes.append({"field": label, "from": old_val or "—", "to": new_val or "—"})

    old_products = before.get("products", [])
    new_products  = after.get("products", [])

    if len(old_products) != len(new_products):
        changes.append({
            "field": "Products",
            "from":  f"{len(old_products)} line(s)",
            "to":    f"{len(new_products)} line(s)",
        })
    else:
        for i, (op, np) in enumerate(zip(old_products, new_products), start=1):
            if op != np:
                changes.append({
                    "field": f"Product line {i}",
                    "from":  f"{op.get('name','')} × {op.get('quantity','')} @ ${op.get('price','')}",
                    "to":    f"{np.get('name','')} × {np.get('quantity','')} @ ${np.get('price','')}",
                })

    return changes


def _append_audit(invoice, event_type, actor, changes=None, note=""):
    """
    Append one JSON entry to invoice.audit_trail and persist it.
    event_type: 'created' | 'edited'
    """
    entry = {
        "event":     event_type,
        "actor":     actor,
        "timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note":      note,
        "changes":   changes or [],
    }
    trail = list(invoice.audit_trail or [])
    trail.append(entry)
    invoice.audit_trail = trail
    invoice.save(update_fields=["audit_trail"])


# ── InvoiceRenderer ───────────────────────────────────────────────────────────

class InvoiceRenderer:
    def __init__(self, invoice):
        self.invoice = invoice
        self.logo_base64 = None
        self._encode_logo()

    def _encode_logo(self):
        try:
            for path in [
                os.path.join(settings.STATIC_ROOT, 'img', 'cc.png'),
                os.path.join(settings.BASE_DIR, 'static', 'img', 'cc.png'),
                os.path.join(settings.BASE_DIR, 'invoices', 'static', 'img', 'cc.png'),
            ]:
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        self.logo_base64 = base64.b64encode(f.read()).decode()
                    break
        except Exception as e:
            print(f"Warning: Could not encode logo: {e}")

    def get_pages_data(self):
        products = self.invoice.products or []
        pages = [products[:11]]
        for i in range(0, len(products[11:]), 19):
            pages.append(products[11:][i:i + 19])
        return {'pages': pages, 'total_pages': len(pages) or 1}

    def get_context(self, preview=True, request=None):
        d = self.get_pages_data()
        return {
            'invoice': self.invoice, 'preview': preview,
            'pages': d['pages'], 'total_pages': d['total_pages'],
            'logo_base64': self.logo_base64, 'request': request,
        }

    def render_pdf(self, request, preview=False):
        html = render_to_string("invoices/inv_template.html", self.get_context(preview=preview))
        buf = io.BytesIO()
        HTML(string=html, base_url=request.build_absolute_uri()).write_pdf(buf)
        return buf.getvalue()


# ── Shared helper ─────────────────────────────────────────────────────────────

def _extract_products(post_data):
    """Parse product table rows from a multivalue POST dict."""
    products = []
    names     = post_data.getlist('product_name')
    quantities = post_data.getlist('quantity')
    discounts  = post_data.getlist('discount')
    prices     = post_data.getlist('price')

    for i in range(len(names)):
        if names[i] and quantities[i] and prices[i]:
            try:
                products.append({
                    'name':             names[i],
                    'quantity':         int(quantities[i]),
                    'discount_percent': float(discounts[i] or 0),
                    'price':            float(prices[i]),
                })
            except (ValueError, TypeError):
                pass
    return products


# ── Views ─────────────────────────────────────────────────────────────────────

def invoice_template(request):
    invoice_id = request.GET.get('id')
    if not invoice_id:
        return redirect('inv_list')
    invoice = get_object_or_404(Invoice, id=invoice_id)
    return render(request, 'invoices/inv_template.html', InvoiceRenderer(invoice).get_context(preview=True))


def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    pdf_bytes = InvoiceRenderer(invoice).render_pdf(request, preview=False)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.folio}.pdf"'
    return response


def invoice_email(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    pdf_bytes = InvoiceRenderer(invoice).render_pdf(request, preview=False)

    recipients = [e for e in [invoice.clt_email, invoice.sell_email] if e]
    if not recipients:
        messages.error(request, "No hay correos configurados para enviar esta factura.")
        return redirect("inv_template")

    email = EmailMessage(
        subject=f"Factura {invoice.folio} - Cabrera Connect",
        body=(
            f"Estimado {invoice.clt_name},\n\n"
            f"Adjuntamos la factura correspondiente a su compra.\n\n"
            f"Gracias por su preferencia.\n"
            f"Atentamente,\nCabrera Connect"
        ),
        from_email="noreply@cabreraconnect.com",
        to=recipients,
    )
    email.attach(f"invoice_{invoice.folio}.pdf", pdf_bytes, "application/pdf")

    try:
        email.send()
        messages.success(request, f"Factura enviada correctamente a: {', '.join(recipients)}")
    except Exception as e:
        messages.error(request, f"Error al enviar el correo: {e}")

    return redirect(f"/invoices/template?id={invoice.id}")


def inv_list(request):
    search_id     = request.GET.get("id", "").strip()
    search_title  = request.GET.get("title", "").strip()
    search_date   = request.GET.get("date", "").strip()
    search_client = request.GET.get("client", "").strip()
    search_seller = request.GET.get("seller", "").strip()
    sort          = request.GET.get("sort", "date")
    direction     = request.GET.get("direction", "desc")

    sort_map = {"id":"id","title":"title","date":"date","amount":"total","client":"clt_name","seller":"sell_name"}
    sort_field = sort_map.get(sort, "date")
    if direction == "desc":
        sort_field = "-" + sort_field

    invoices = Invoice.objects.all().order_by(sort_field)
    if search_id:     invoices = invoices.filter(id__icontains=search_id)
    if search_title:  invoices = invoices.filter(title__icontains=search_title)
    if search_date:   invoices = invoices.filter(date=search_date)
    if search_client: invoices = invoices.filter(clt_name__icontains=search_client)
    if search_seller: invoices = invoices.filter(sell_name__icontains=search_seller)

    for inv in invoices:
        if inv.total is None or isinstance(inv.total, str):
            try:
                inv.calculate_totals(); inv.save()
            except Exception:
                inv.subtotal = inv.total_discount = inv.total_tax = inv.total = Decimal("0.00")
                inv.save()

    total_sales = invoices.aggregate(total_amount=Sum("total"))["total_amount"] or Decimal("0.00")

    per_page = request.GET.get("per_page", 15)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 15

    paginator = Paginator(invoices, per_page)
    page_obj  = paginator.get_page(request.GET.get("page"))

    return render(request, "invoices/inv_list.html", {
        "invoices": page_obj, "page_obj": page_obj,
        "total_sales": total_sales, "per_page": per_page,
        "per_page_options": [15, 25, 50, 100],
        "search_params": {
            "id": search_id, "title": search_title, "date": search_date,
            "client": search_client, "seller": search_seller,
        },
        "sort": sort, "direction": direction,
    })


def inv_crt(request):
    # AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'POST':
        try:
            data = json.loads(request.body)
            return JsonResponse({'success': True, 'product': {
                'name': data.get('name', ''),
                'price': Decimal(data.get('price', 0)),
                'quantity': int(data.get('quantity', 1)),
                'discount_percent': Decimal(data.get('discount_percent', 0)),
            }})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    if request.method == 'POST':
        products  = _extract_products(request.POST)
        post_data = request.POST.copy()
        post_data['products_json'] = json.dumps(products)
        form = InvoiceForm(post_data)

        if form.is_valid():
            invoice = form.save()

            # ── AUDIT: created ─────────────────────────────────────
            _append_audit(
                invoice,
                event_type="created",
                actor=_get_actor(request),
                note=f"Invoice #{invoice.folio} created.",
            )

            messages.success(request, f"Invoice #{invoice.folio} created successfully!")
            return redirect(f'{reverse("inv_template")}?id={invoice.id}&download=true')

        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f'{field.replace("_", " ").title()}: {err}')

        return render(request, 'invoices/inv_crt.html', {
            'form': form,
            'default_tax_rate': Invoice._meta.get_field('tax_rate').default,
            'submitted_products': products,
        })

    return render(request, 'invoices/inv_crt.html', {
        'form': InvoiceForm(),
        'default_tax_rate': Invoice._meta.get_field('tax_rate').default,
        'submitted_products': [],
    })


def inv_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    # AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            if action == 'add_product':
                invoice.add_product({
                    'name': data.get('name', ''),
                    'price': Decimal(data.get('price', 0)),
                    'quantity': int(data.get('quantity', 1)),
                    'discount_percent': Decimal(data.get('discount_percent', 0)),
                })
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
        before    = _snapshot_fields(invoice)           # snapshot BEFORE save
        products  = _extract_products(request.POST)
        post_data = request.POST.copy()
        post_data['products_json'] = json.dumps(products)
        form = InvoiceForm(post_data, instance=invoice)

        if form.is_valid():
            updated = form.save()
            after   = _snapshot_fields(updated)          # snapshot AFTER save
            changes = _diff_snapshots(before, after)

            # ── AUDIT: edited ──────────────────────────────────────
            _append_audit(
                updated,
                event_type="edited",
                actor=_get_actor(request),
                changes=changes,
                note="" if changes else f"Invoice #{updated.folio} saved with no field changes.",
            )

            messages.success(request, f"Invoice #{updated.folio} updated successfully!")
            return redirect(f'{reverse("inv_template")}?id={updated.id}')

        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, f'{field.replace("_", " ").title()}: {err}')

        return render(request, 'invoices/inv_edit.html', {
            'form': form, 'invoice': invoice,
            'default_tax_rate': Invoice._meta.get_field('tax_rate').default,
            'submitted_products': products,
            'audit_trail': invoice.audit_trail or [],
        })

    # GET
    products_list = invoice.products if isinstance(invoice.products, list) else []

    return render(request, 'invoices/inv_edit.html', {
        'form': InvoiceForm(instance=invoice),
        'invoice': invoice,
        'default_tax_rate': Invoice._meta.get_field('tax_rate').default,
        'submitted_products': products_list,
        'audit_trail': invoice.audit_trail or [],
    })


def inv_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        invoice.delete()
        return redirect('inv_list')
    return render(request, 'invoices/inv_delete.html', {'invoice': invoice})

def dashboard(request):
    """Analytics dashboard — all metrics derived from Invoice data."""
    from collections import defaultdict
    import json

    date_range      = request.GET.get('date_range', 'year')
    property_filter = request.GET.get('property', '')

    # ── Base queryset ──────────────────────────────────────────────
    invoices = Invoice.objects.all()
    if property_filter:
        invoices = invoices.filter(property=property_filter)

    today = timezone.now().date()
    if date_range == 'week':
        invoices = invoices.filter(date__gte=today - timedelta(days=7))
    elif date_range == 'month':
        invoices = invoices.filter(date__gte=today - timedelta(days=30))
    elif date_range == 'year':
        invoices = invoices.filter(date__gte=today - timedelta(days=365))

    # ── KPI cards ──────────────────────────────────────────────────
    total_invoices    = invoices.count()
    total_revenue     = invoices.aggregate(t=Sum('total'))['t']         or Decimal('0')
    avg_invoice_value = total_revenue / total_invoices if total_invoices else Decimal('0')
    unique_clients    = invoices.values('clt_email').distinct().count()

    # ── Monthly trend ──────────────────────────────────────────────
    monthly_qs = (
        Invoice.objects.filter(date__gte=today - timedelta(days=365))
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('total'), count=Count('id'))
        .order_by('month')
    )
    monthly_labels = [item['month'].strftime('%b %Y') for item in monthly_qs] or ['No data']
    monthly_totals = [float(item['total'])             for item in monthly_qs] or [0]

    # ── Daily (last 30 days) ───────────────────────────────────────
    daily_qs = (
        Invoice.objects.filter(date__gte=today - timedelta(days=30))
        .values('date')
        .annotate(total=Sum('total'))
        .order_by('date')
    )
    daily_labels = [str(item['date'])     for item in daily_qs] or ['No data']
    daily_totals = [float(item['total'])  for item in daily_qs] or [0]

    # ── Property type breakdown ────────────────────────────────────
    PROPERTY_DISPLAY = dict(Invoice.PROPERTY)
    property_qs = (
        invoices.values('property')
        .annotate(total=Sum('total'), count=Count('id'))
        .order_by('-total')
    )
    total_rev_all = float(total_revenue) or 1  # avoid div/0
    property_table = []
    for row in property_qs:
        pct = round(float(row['total']) / total_rev_all * 100, 1)
        property_table.append({
            'type':  row['property'],
            'label': PROPERTY_DISPLAY.get(row['property'], row['property']),
            'count': row['count'],
            'total': row['total'],
            'pct':   pct,
        })

    property_labels = [r['label']        for r in property_table] or ['No data']
    property_totals = [float(r['total']) for r in property_table] or [0]

    # ── Payment methods ────────────────────────────────────────────
    PAYMENT_DISPLAY = dict(Invoice.PAY_METHOD)
    payment_qs = (
        invoices.values('payment_method')
        .annotate(total=Sum('total'), count=Count('id'))
        .order_by('-total')
    )
    payment_table = [{
        'method': row['payment_method'],
        'label':  PAYMENT_DISPLAY.get(row['payment_method'], row['payment_method']),
        'count':  row['count'],
        'total':  row['total'],
    } for row in payment_qs]

    payment_labels = [r['label']        for r in payment_table] or ['No data']
    payment_totals = [float(r['total']) for r in payment_table] or [0]

    # ── Currency stats ─────────────────────────────────────────────
    currency_stats = (
        invoices.values('currency')
        .annotate(total=Sum('total'), count=Count('id'))
        .order_by('-total')
    )

    # ── Tax summary ────────────────────────────────────────────────
    agg = invoices.aggregate(
        subtotal=Sum('subtotal'),
        discounts=Sum('total_discount'),
        tax=Sum('total_tax'),
        net=Sum('total'),
    )
    tax_summary = {
        'subtotal':  agg['subtotal']  or Decimal('0'),
        'discounts': agg['discounts'] or Decimal('0'),
        'tax':       agg['tax']       or Decimal('0'),
        'net':       agg['net']       or Decimal('0'),
    }

    # ── Top clients & sellers ──────────────────────────────────────
    top_clients = (
        invoices.values('clt_name', 'clt_email')
        .annotate(total_spent=Sum('total'), invoice_count=Count('id'))
        .order_by('-total_spent')[:10]
    )
    top_sellers = (
        invoices.values('sell_name', 'sell_email')
        .annotate(total_sales=Sum('total'), invoice_count=Count('id'))
        .order_by('-total_sales')[:10]
    )

    # ── Product analytics (iterate JSON field) ─────────────────────
    product_agg = defaultdict(lambda: {'total_qty': 0, 'total_rev': 0.0})
    for inv in invoices.only('products'):
        for item in (inv.products or []):
            name = item.get('name', '').strip()
            if not name:
                continue
            qty   = float(item.get('quantity', 1) or 1)
            price = float(item.get('price', 0) or 0)
            disc  = float(item.get('discount_percent', 0) or 0)
            rev   = qty * price * (1 - disc / 100)
            product_agg[name]['total_qty'] += qty
            product_agg[name]['total_rev'] += rev

    product_list = [
        {'name': name, 'total_qty': int(v['total_qty']), 'total_rev': round(v['total_rev'], 2)}
        for name, v in product_agg.items()
    ]
    top_products_qty = sorted(product_list, key=lambda x: x['total_qty'], reverse=True)[:10]
    top_products_rev = sorted(product_list, key=lambda x: x['total_rev'], reverse=True)[:10]

    # ── Recent invoices ────────────────────────────────────────────
    recent_invoices = invoices.order_by('-date', '-id')[:15]

    # ── Context ────────────────────────────────────────────────────
    return render(request, 'invoices/dashboard.html', {
        # KPIs
        'total_invoices':    total_invoices,
        'total_revenue':     total_revenue,
        'avg_invoice_value': avg_invoice_value,
        'unique_clients':    unique_clients,

        # Charts (JSON strings for JS)
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_totals': json.dumps(monthly_totals),
        'daily_labels':   json.dumps(daily_labels),
        'daily_totals':   json.dumps(daily_totals),
        'property_labels':json.dumps(property_labels),
        'property_totals':json.dumps(property_totals),
        'payment_labels': json.dumps(payment_labels),
        'payment_totals': json.dumps(payment_totals),

        # Tables
        'property_table':   property_table,
        'payment_table':    payment_table,
        'currency_stats':   currency_stats,
        'tax_summary':      tax_summary,
        'top_clients':      top_clients,
        'top_sellers':      top_sellers,
        'top_products_qty': top_products_qty,
        'top_products_rev': top_products_rev,
        'recent_invoices':  recent_invoices,

        # Filters
        'date_range':       date_range,
        'property_filter':  property_filter,
        'property_choices': Invoice.PROPERTY,
    })