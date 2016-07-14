from geonode.layers.models import Layer
from geonode.base.models import Link
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
import sys

def tileset_post_save(instance, sender, **kwargs):
    try:
        existing_layer = Layer.objects.filter(name=instance.name).exists()

        if not existing_layer:
            layer = Layer(name=instance.name)
            layer.save()
        else:
            layer = Layer.objects.get(name=instance.name)     
               
        tile_url = "/djmp/%d/map/tiles/%s/EPSG3857/{z}/{x}/{y}.png" % (instance.id, instance.name)
        l, __ = Link.objects.get_or_create(
            resource=layer.resourcebase_ptr,
            defaults=dict(
                extension='tiles',
                name="Tiles",
                mime='image/png',
                link_type='image'
            )
        )
        l.tile_url = tile_url
        l.save()
    except:
        print sys.exc_info()[0]
