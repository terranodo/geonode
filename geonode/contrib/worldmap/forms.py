import json

from django import forms


GEOMETRY_CHOICES = [
    ['Point', 'Points'],
    ['LineString', 'Lines'],
    ['Polygon', 'Polygons (Shapes)']
]


class JSONField(forms.CharField):
    def clean(self, text):
        text = super(JSONField, self).clean(text)
        try:
            return json.loads(text)
        except ValueError:
            raise forms.ValidationError("this field must be valid JSON")


class LayerCreateForm(forms.Form):
    name = forms.CharField(label="Name", max_length=256,required=True)
    title = forms.CharField(label="Title",max_length=256,required=True)
    srs = forms.CharField(label="Projection",initial="EPSG:4326",required=True)
    geom = forms.ChoiceField(label="Data type", choices=GEOMETRY_CHOICES,required=True)
    keywords = forms.CharField(label = '*' + ('Keywords (separate with spaces)'), widget=forms.Textarea)
    abstract = forms.CharField(widget=forms.Textarea, label="Abstract", required=True)
    permissions = JSONField()