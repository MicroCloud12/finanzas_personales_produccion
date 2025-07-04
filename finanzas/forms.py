from django import forms
from .models import registro_transacciones
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class TransaccionesForm (forms.ModelForm):
    class Meta():
        model = registro_transacciones
        # En lugar de listar los campos que queremos, listamos los que NO queremos.
        # Esto oculta el campo 'propietario' del formulario.
        exclude = ('propietario',)
        # --- AQUÍ ESTÁ LA NUEVA MAGIA ---
        # Definimos explícitamente qué widget y qué atributos
        # queremos para cada campo del formulario.
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date','class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'categoria': forms.TextInput(attrs={'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'monto': forms.NumberInput(attrs={'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'tipo': forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'cuenta_origen': forms.TextInput(attrs={'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'cuenta_destino': forms.TextInput(attrs={'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'id_prestamo_ref': forms.TextInput(attrs={'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
        }

    # --- AÑADIMOS ESTA LÓGICA DE ESTILOS ---
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # Definimos las clases para los campos de texto, fecha, número, etc.
            tailwind_input_classes = "appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            # Clases para el menú desplegable (select)
            tailwind_select_classes = "block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"

            # Iteramos sobre todos los campos para aplicar las clases
            for field_name, field in self.fields.items():
                if field.widget.input_type == 'select':
                    # Si el campo es un menú desplegable (como nuestro campo 'tipo')
                    field.widget.attrs.update({'class': tailwind_select_classes})
                else:
                    # Para todos los demás campos
                    field.widget.attrs.update({'class': tailwind_input_classes})


class FormularioRegistroPersonalizado(UserCreationForm):
    # El campo de email y la validación que ya teníamos están perfectos.
    email = forms.EmailField(
        required=True,
        help_text='Obligatorio. Introduce una dirección de correo válida.'
    )

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    # --- AQUÍ VIENE LA NUEVA LÓGICA ---
    # Sobrescribimos el método de inicialización del formulario
    def __init__(self, *args, **kwargs):
        # Primero, ejecutamos la inicialización original
        super().__init__(*args, **kwargs)

        # Ahora, definimos las clases de Tailwind que queremos aplicar
        tailwind_classes = "appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"

        # Iteramos sobre todos los campos del formulario
        for field_name, field in self.fields.items():
            # Y le añadimos las clases a su widget (el input HTML)
            field.widget.attrs.update({'class': tailwind_classes})

    def clean_email(self):
        # Esta función de validación sigue igual
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este correo electrónico ya está en uso.")
        return email
