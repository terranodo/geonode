from django.db import models
from django.db.models import signals

from djmp.models import Tileset
from geonode.layers.models import Layer
from geonode.base.models import Link

from geonode.contrib.mp.signals import tileset_post_save 

signals.post_save.connect(tileset_post_save, sender=Tileset)
