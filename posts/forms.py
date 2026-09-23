from django import forms

from posts.models import Post
from posts.services import create_post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ("content", "image", "location")
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 3, "maxlength": Post.MAX_CONTENT_LENGTH, "placeholder": "What's happening?"}
            ),
            "location": forms.TextInput(attrs={"placeholder": "Add a location (optional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # content/image constraints are enforced by the service layer.
        self.fields["content"].required = False
        self.fields["image"].required = False

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("content") or "").strip() and not cleaned.get("image"):
            raise forms.ValidationError("Write something or attach an image.")
        return cleaned

    def save(self, commit: bool = True) -> Post:
        """Route through the service so moderation is always queued."""
        return create_post(
            author=self.instance.author,
            content=self.cleaned_data.get("content", ""),
            image=self.cleaned_data.get("image"),
            location=self.cleaned_data.get("location", ""),
        )


class PostEditForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ("content", "image", "location")
        widgets = {
            "content": forms.Textarea(attrs={"rows": 3, "maxlength": Post.MAX_CONTENT_LENGTH}),
        }

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("content") or "").strip() and not cleaned.get("image"):
            raise forms.ValidationError("A post needs text or an image.")
        return cleaned
