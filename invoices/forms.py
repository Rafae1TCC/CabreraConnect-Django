# forms.py
from django import forms
from .models import Invoice
import json
from datetime import datetime

class InvoiceForm(forms.ModelForm):
    products_json = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial='[]'
    )

    class Meta:
        model = Invoice
        fields = [
            'title',
            'date',
            'clt_name',
            'clt_email',
            'clt_phone',
            'sell_name',
            'sell_email',
            'sell_phone',
            'comments',
            'currency',
            'payment_method',
            'property',  # ← AÑADIR ESTA LÍNEA
            'tax_rate',
            'exchange_rate',
            'warranty_months',
        ]
        
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'comments': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'tax_rate': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'exchange_rate': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'property': forms.Select(attrs={'class': 'form-control'}),  # ← AÑADIR ESTA LÍNEA
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        # Mark required fields
        for field_name in ['clt_name', 'clt_email', 'sell_name', 'sell_email', 'title']:
            if field_name in self.fields:
                self.fields[field_name].required = True
                self.fields[field_name].widget.attrs['required'] = 'required'
        
        # Placeholders
        placeholders = {
            'title': 'Invoice title (e.g., "Security System Installation")',
            'clt_name': 'Full name of the client',
            'clt_email': 'client@example.com',
            'clt_phone': '(664) 123-4567',
            'sell_name': 'Full name of the seller/agent',
            'sell_email': 'seller@cabreraconnect.com',
            'sell_phone': '(664) 123-4567',
            'comments': 'Any additional notes or instructions...',
            'warranty_months': 'Number of months (e.g., 12)',
        }
        
        for field_name, field in self.fields.items():
            if field_name != 'products_json':
                if 'class' not in field.widget.attrs:
                    field.widget.attrs['class'] = 'form-control'
                
                if field_name in placeholders and field_name not in ['date']:
                    if hasattr(field.widget, 'attrs'):
                        field.widget.attrs['placeholder'] = placeholders[field_name]
        
        # Date formatting
        if instance and instance.date:
            self.fields['date'].initial = instance.date.strftime('%Y-%m-%d')
        elif not instance and not self.is_bound:
            self.fields['date'].initial = datetime.now().strftime('%Y-%m-%d')
        
        if instance:
            self.fields['products_json'].initial = json.dumps(instance.products)
        
        # Default values
        if not instance or not self.is_bound:
            self.fields['currency'].initial = 'MXN'
            self.fields['payment_method'].initial = 'cash'
            self.fields['property'].initial = 'residential'
            self.fields['tax_rate'].initial = 16.00
            self.fields['exchange_rate'].initial = 18.00
            self.fields['warranty_months'].initial = 0

    def clean_clt_email(self):
        """Validate client email format"""
        email = self.cleaned_data.get('clt_email')
        if email and '@' not in email:
            raise forms.ValidationError("Please enter a valid email address (e.g., name@domain.com)")
        return email

    def clean_sell_email(self):
        """Validate seller email format"""
        email = self.cleaned_data.get('sell_email')
        if email and '@' not in email:
            raise forms.ValidationError("Please enter a valid email address (e.g., name@domain.com)")
        return email

    def clean_date(self):
        """Ensure date is properly formatted"""
        date = self.cleaned_data.get('date')
        if isinstance(date, str):
            try:
                return datetime.strptime(date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                raise forms.ValidationError("Invalid date format. Use YYYY-MM-DD.")
        return date

    def clean_tax_rate(self):
        """Validate tax rate is between 0 and 100"""
        tax_rate = self.cleaned_data.get('tax_rate')
        if tax_rate is not None and (tax_rate < 0 or tax_rate > 100):
            raise forms.ValidationError("Tax rate must be between 0 and 100 percent")
        return tax_rate

    def clean_exchange_rate(self):
        """Validate exchange rate is positive"""
        exchange_rate = self.cleaned_data.get('exchange_rate')
        if exchange_rate is not None and exchange_rate <= 0:
            raise forms.ValidationError("Exchange rate must be greater than 0")
        return exchange_rate

    def clean_warranty_months(self):
        """Validate warranty months is non-negative"""
        warranty = self.cleaned_data.get('warranty_months')
        if warranty is not None and warranty < 0:
            raise forms.ValidationError("Warranty months cannot be negative")
        return warranty

    def clean_products_json(self):
        data = self.cleaned_data.get('products_json', '[]')
        try:
            if isinstance(data, list):
                products = data
            else:
                products = json.loads(data) if data else []
            
            if not isinstance(products, list):
                raise forms.ValidationError("Products data must be a list")
            
            # Validate each product
            for idx, product in enumerate(products):
                if not product.get('name'):
                    raise forms.ValidationError(f"Product #{idx + 1}: Name is required")
                if not product.get('price') or float(product.get('price', 0)) <= 0:
                    raise forms.ValidationError(f"Product #{idx + 1}: Price must be greater than 0")
                if not product.get('quantity') or int(product.get('quantity', 0)) <= 0:
                    raise forms.ValidationError(f"Product #{idx + 1}: Quantity must be greater than 0")
                if product.get('discount_percent', 0) < 0 or product.get('discount_percent', 0) > 100:
                    raise forms.ValidationError(f"Product #{idx + 1}: Discount must be between 0 and 100")
            
            return products
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid products data format")

    def save(self, commit=True):
        instance = super().save(commit=False)
        products = self.cleaned_data.get('products_json', [])
        
        # Clear existing products and add new ones
        instance.products = []
        for product in products:
            instance.add_product(product)
        
        # Calculate totals before saving
        instance.calculate_totals()
        
        if commit:
            instance.save()
        return instance