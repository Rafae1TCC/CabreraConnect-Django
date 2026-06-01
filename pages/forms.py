from django import forms

SERVICE_CHOICES = [
    ('cctv',       'CCTV & IP Cameras'),
    ('nvr_dvr',    'NVRs & DVRs / Recording Systems'),
    ('access',     'Access Control'),
    ('alarms',     'Alarms & Intrusion Detection'),
    ('iot_gps',    'IoT & GPS Tracking'),
    ('networking', 'Network Infrastructure'),
]

class QuoteForm(forms.Form):
    # ── Contact info ────────────────────────────────────────────────
    name = forms.CharField(
        max_length=120,
        label='Full Name',
        widget=forms.TextInput(attrs={'placeholder': 'John Doe'}),
    )
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'placeholder': 'john@example.com'}),
    )
    phone = forms.CharField(
        max_length=20,
        label='Phone / WhatsApp Number',
        widget=forms.TextInput(attrs={'placeholder': '+52 664 000 0000'}),
    )

    # ── Installation address ────────────────────────────────────────
    address = forms.CharField(
        label='Installation Address',
        widget=forms.TextInput(attrs={'placeholder': 'Street, City, State'}),
    )
    property_type = forms.ChoiceField(
        label='Property Type',
        choices=[
            ('', '— Select one —'),
            ('residential', 'Residential'),
            ('commercial',  'Commercial'),
            ('industrial',  'Industrial'),
            ('government',  'Government / Institutional'),
            ('other',       'Other'),
        ],
    )

    # ── Services ────────────────────────────────────────────────────
    services = forms.MultipleChoiceField(
        label='Services Required',
        choices=SERVICE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text='Select all that apply.',
    )

    # ── Job description ─────────────────────────────────────────────
    description = forms.CharField(
        label='Project Description',
        widget=forms.Textarea(attrs={
            'placeholder': (
                'Describe the scope of work: number of cameras, '
                'coverage areas, special requirements, etc.'
            ),
            'rows': 5,
        }),
    )