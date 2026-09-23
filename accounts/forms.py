from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from accounts.models import User


class SignUpForm(UserCreationForm):
    """Session-based signup for the template UI (mirrors RegisterSerializer)."""

    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username or email")

    def clean(self):
        identifier = self.cleaned_data.get("username", "").strip()
        if identifier and "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
            if user:
                self.cleaned_data["username"] = user.username
        return super().clean()


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("display_name", "bio", "location", "website", "avatar", "is_private")
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
            "is_private": forms.CheckboxInput(),
        }
