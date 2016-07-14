from geonode.layers.models import Layer
from geonode.base.models import Link
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.conf import settings
import sys

from .settings import USE_DISK_CACHE
from djmp.settings import FILE_CACHE_DIRECTORY
from .models import Tileset

def tileset_post_save(instance, sender, **kwargs):
    try:
        existing_layer = Layer.objects.filter(name=instance.name).exists()

        if not existing_layer:
            layer = Layer(name=instance.name)
            layer.bbox_x0 = instance.bbox_x0
            layer.bbox_x1 = instance.bbox_x1
            layer.bbox_y0 = instance.bbox_y0
            layer.bbox_y1 = instance.bbox_y1
            layer.save()
        else:
            layer = Layer.objects.get(name=instance.name)     
        
        if USE_DISK_CACHE:
            tile_url = '/%s/%s/{z}/{x}/{y}.png' % (FILE_CACHE_DIRECTORY, instance.id)
        else:
            tile_url = "/djmp/%d/map/tiles/%s/EPSG3857/{z}/{x}/{y}.png" % (instance.id, instance.name)

        l, __ = Link.objects.get_or_create(
            resource=layer.resourcebase_ptr,
            extension='tiles',
            name="Tiles",
            mime='image/png',
            link_type='image'
        )

        l.url = tile_url
        l.save()
    except:
        print sys.exc_info()[0]

def layer_post_save(instance, sender, **kwargs):
    tileset, __ = Tileset.objects.get_or_create(
        name = instance.title,
        created_by = instance.owner.username,
        source_type = 'wms',
        server_url = settings.OGC_SERVER['default']['LOCATION'] + 'wms',
        server_username = settings.OGC_SERVER['default']['USER'],
        server_password = settings.OGC_SERVER['default']['PASSWORD'],
        layer_name = instance.typename,
        layer_zoom_stop = 12,
        bbox_x0 = instance.bbox_x0,
        bbox_x1 = instance.bbox_x1,
        bbox_y0 = instance.bbox_y0,
        bbox_y1 = instance.bbox_y1,
        cache_type = 'file',
        directory_layout = 'tms'
        )
    tileset.seed()
