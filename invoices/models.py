from decimal import Decimal, InvalidOperation
from django.db import models
from django.db.models import JSONField

class Invoice(models.Model):
    CURRENCY = [
        ('MXN', 'Pesos Mexicanos'),
        ('USD', 'Dolares'),
    ]

    PAY_METHOD = [
        ('cash', 'Efectivo'),
        ('card', 'Tarjeta de crédito/débito'),
        ('transfer', 'Transferencia bancaria'),
    ]

    # Selling information
    title = models.CharField(max_length=128)
    folio = models.CharField(max_length=20, unique=True, blank=True)  # Auto-generated folio
    date = models.DateField()
    
    # Client information
    clt_name = models.CharField(max_length=64)
    clt_email = models.EmailField(max_length=64)
    clt_phone = models.CharField(max_length=15)
    
    # Seller information
    sell_name = models.CharField(max_length=64)
    sell_email = models.EmailField(max_length=64)
    sell_phone = models.CharField(max_length=15)

    # Payment Details
    comments = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=16, choices=CURRENCY, default='MXN')
    payment_method = models.CharField(max_length=16, choices=PAY_METHOD, default='cash')
    tax_rate = models.DecimalField(decimal_places=2, max_digits=5, default=16.00)
    exchange_rate = models.DecimalField(decimal_places=2, max_digits=10, default=18)
    warranty_months = models.IntegerField(default=0)

    # Products information (stored as JSON)
    products = JSONField(default=list)  # Stores all product details directly
    
    # Calculated totals
    subtotal = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    total_discount = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    total_tax = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    total = models.DecimalField(decimal_places=2, max_digits=10, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.folio} - {self.title}"
    
    def add_product(self, product_data):
        """
        Add a product to the invoice with all its details.
        product_data should be a dict containing:
        {
            'name': str, 
            'price': Decimal,
            'quantity': int,
            'discount_percent': Decimal (optional, default=0),
        }
        """
        if not hasattr(self, 'products') or self.products is None:
            self.products = []
            
        # Set defaults
        product_data.setdefault('discount_percent', 0)
        product_data.setdefault('discount_amount', 0)
        product_data.setdefault('taxable', True)
        product_data.setdefault('warranty_months', 0)
        
        self.products.append(product_data)
    
    def calculate_totals(self):
        """Calculate and update all financial totals based on products"""
        subtotal = Decimal('0')
        total_discount = Decimal('0')
        total_tax = Decimal('0')
        
        # Handle case where products is None or empty
        if not self.products:
            self.products = []
        
        for product in self.products:
            # Safely convert values to Decimal with defaults
            quantity = self._safe_decimal(product.get('quantity', 1))
            price = self._safe_decimal(product.get('price', 0))
            discount_percent = self._safe_decimal(product.get('discount_percent', 0))
            discount_amount = self._safe_decimal(product.get('discount_amount', 0))
            
            # Calculate line totals
            line_subtotal = price * quantity
            
            # Calculate discounts
            if discount_percent > 0:
                line_discount = line_subtotal * (discount_percent / 100)
            else:
                line_discount = discount_amount
                
            line_total = line_subtotal - line_discount
            
            # Calculate tax if applicable
            tax_rate = self._safe_decimal(self.tax_rate)
            if product.get('taxable', True):
                line_tax = line_total * (tax_rate / 100)
            else:
                line_tax = Decimal('0')
            
            # Update aggregates
            subtotal += line_subtotal
            total_discount += line_discount
            total_tax += line_tax
            
            # Update product entry with calculated values
            product['line_subtotal'] = float(line_subtotal)
            product['line_discount'] = float(line_discount)
            product['line_total'] = float(line_total)
            product['line_tax'] = float(line_tax)
        
        # Update model fields with safe defaults
        self.subtotal = subtotal
        self.total_discount = total_discount
        self.total_tax = total_tax
        self.total = subtotal - total_discount + total_tax
    
    def _safe_decimal(self, value, default=0):
        """Safely convert a value to Decimal, handling None and invalid values"""
        if value is None:
            return Decimal(str(default))
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal(str(default))
    
    def save(self, *args, **kwargs):
        # Auto-generate folio if not provided
        if not self.folio:
            last_invoice = Invoice.objects.filter(folio__startswith='COT-').order_by('folio').last()
            if last_invoice:
                try:
                    last_number = int(last_invoice.folio.split('-')[1])
                    self.folio = f'COT-{last_number + 1:04d}'
                except (IndexError, ValueError):
                    self.folio = 'COT-0001'
            else:
                self.folio = 'COT-0001'
        
        # Ensure all decimal fields have valid values before saving
        self.subtotal = self._safe_decimal(self.subtotal)
        self.total_discount = self._safe_decimal(self.total_discount)
        self.total_tax = self._safe_decimal(self.total_tax)
        self.total = self._safe_decimal(self.total)
        self.tax_rate = self._safe_decimal(self.tax_rate, 16.00)
        self.exchange_rate = self._safe_decimal(self.exchange_rate, 18)
        
        # Calculate totals before saving
        self.calculate_totals()
        super().save(*args, **kwargs)
    
    def get_product_summary(self):
        """Return a summary of all products with calculated values"""
        return self.products
    
    def clear_products(self):
        """Remove all products from the invoice"""
        self.products = []