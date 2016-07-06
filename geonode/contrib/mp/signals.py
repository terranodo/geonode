from geonode.layers.models import Layer
from django.core.exceptions import ObjectDoesNotExist
import sys

def tileset_post_save(instance, sender, **kwargs):
    try:
        existing_layer = Layer.objects.get(name=instance.name) 
    except ObjectDoesNotExist:
        layer = Layer(name=instance.name)
        layer.save()
    except:
        print sys.exc_info()[0]
