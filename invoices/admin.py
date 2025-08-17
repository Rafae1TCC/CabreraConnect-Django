from django.contrib import admin
from .models import Invoice

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['folio', 'title', 'date', 'total', 'currency']
    list_filter = ['currency', 'payment_method', 'date']
    search_fields = ['folio', 'title', 'clt_name', 'sell_name']
    readonly_fields = ['folio', 'created_at', 'updated_at']
    ordering = ['-created_at']
    fieldsets = (
        (None, {
            'fields': ('title', 'date', 'folio')
        }),
        ('Client Information', {
            'fields': ('clt_name', 'clt_email', 'clt_phone')
        }),
        ('Seller Information', {
            'fields': ('sell_name', 'sell_email', 'sell_phone')
        }),
        ('Payment Details', {
            'fields': ('comments', 'currency', 'payment_method', 'tax_rate', 'exchange_rate', 'warranty_months')
        }),
        ('Totals', {
            'fields': ('subtotal', 'total_discount', 'total_tax', 'total')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
