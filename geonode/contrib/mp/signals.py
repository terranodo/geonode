from geonode.layers.models import Layer
from geonode.base.models import Link
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
import sys

def tileset_post_save(instance, sender, **kwargs):
    try:
        existing_layer = Layer.objects.get(name=instance.name) 
    except ObjectDoesNotExist:
        layer = Layer(name=instance.name)
        layer.save()
        #tile_url = reverse('tileset_mapproxy', kwargs={'pk':instance.id, 'path_info':'abc'})
        tile_url = "abc" 

        Link.objects.get_or_create(
            resource=layer.resourcebase_ptr,
            url=tile_url,
            defaults=dict(
                extension='tiles',
                name="Tiles",
                mime='image/png',
                link_type='image'
            )
        )
    except:
        print sys.exc_info()[0]
