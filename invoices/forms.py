from django import forms
from .models import Invoice
import json

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
            'tax_rate',
            'exchange_rate',
            'warranty_months',
        ]
        
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'comments': forms.Textarea(attrs={'rows': 3}),
            'tax_rate': forms.NumberInput(attrs={'step': '0.01'}),
            'exchange_rate': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        if instance:
            self.fields['products_json'].initial = json.dumps(instance.products)
        
        # Set currency and payment method defaults
        self.fields['currency'].initial = 'MXN'
        self.fields['payment_method'].initial = 'cash'

    def clean_products_json(self):
        data = self.cleaned_data['products_json']
        try:
            products = json.loads(data)
            if not isinstance(products, list):
                raise forms.ValidationError("Products data must be a list")
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
        
        if commit:
            instance.save()
        return instance