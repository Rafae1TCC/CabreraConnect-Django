from decimal import Decimal
from django.db import models
from django.db.models import JSONField

class Invoice(models.Model):
    CURRENCY = [
        ('MXN', 'Mexican Pesos'),
        ('USD', 'Dollars'),
    ]

    PAY_METHOD = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Bank transfer'),
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

    def save(self, *args, **kwargs):
        # Auto-generate folio if not provided
        if not self.folio:
            last_invoice = Invoice.objects.filter(folio__startswith='COT-').order_by('folio').last()
            if last_invoice:
                last_number = int(last_invoice.folio.split('-')[1])
                self.folio = f'COT-{last_number + 1:04d}'
            else:
                self.folio = 'COT-0001'
        
        # Calculate totals before saving
        self.calculate_totals()
        super().save(*args, **kwargs)

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
        
        for product in self.products:
            quantity = Decimal(str(product.get('quantity', 1)))
            price = Decimal(str(product.get('price', 0)))
            
            # Calculate line totals
            line_subtotal = price * quantity
            
            # Calculate discounts
            discount_percent = Decimal(str(product.get('discount_percent', 0)))
            discount_amount = Decimal(str(product.get('discount_amount', 0)))
            
            if discount_percent > 0:
                line_discount = line_subtotal * (discount_percent / 100)
            else:
                line_discount = discount_amount
                
            line_total = line_subtotal - line_discount
            
            # Calculate tax if applicable
            if product.get('taxable', True):
                line_tax = line_total * (Decimal(str(self.tax_rate)) / 100)
            else:
                line_tax = Decimal('0')
            
            # Update aggregates
            subtotal += line_subtotal
            total_discount += line_discount
            total_tax += line_tax
            
            # Update product entry with calculated values
            product['line_subtotal'] = str(line_subtotal)
            product['line_discount'] = str(line_discount)
            product['line_total'] = str(line_total)
            product['line_tax'] = str(line_tax)
        
        # Update model fields
        self.subtotal = subtotal
        self.total_discount = total_discount
        self.total_tax = total_tax
        self.total = subtotal - total_discount + total_tax
    
    def get_product_summary(self):
        """Return a summary of all products with calculated values"""
        return self.products
    
    def clear_products(self):
        """Remove all products from the invoice"""
        self.products = []