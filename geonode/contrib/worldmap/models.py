from django.db import models
from django.utils.translation import ugettext_lazy as _

from geonode.layers.models import Layer
from geonode.maps.models import Map


class MapStats(models.Model):
    map = models.ForeignKey(Map, unique=True)
    visits = models.IntegerField(_("Visits"), default= 0)
    uniques = models.IntegerField(_("Unique Visitors"), default = 0)
    last_modified = models.DateTimeField(auto_now=True,null=True)

    class Meta:
        verbose_name_plural = 'Map stats'


class LayerStats(models.Model):
    layer = models.ForeignKey(Layer, unique=True)
    visits = models.IntegerField(_("Visits"), default = 0)
    uniques = models.IntegerField(_("Unique Visitors"), default = 0)
    downloads = models.IntegerField(_("Downloads"), default = 0)
    last_modified = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name_plural = 'Layer stats'


class SocialExplorerLocation(models.Model):
    map = models.ForeignKey(Map, related_name="jump_set")
    url = models.URLField(_("Jump URL"), blank=False, null=False, default='http://www.socialexplorer.com/pub/maps/map3.aspx?g=0&mapi=SE0012&themei=B23A1CEE3D8D405BA2B079DDF5DE9402')
    title = models.TextField(_("Jump Site"), blank=False, null=False)

    def json(self):
        logger.debug("JSON url: %s", self.url)
        return {
            "url": self.url,
            "title" :  self.title
        }