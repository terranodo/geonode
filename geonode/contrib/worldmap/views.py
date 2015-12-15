import json

from django.http import HttpResponse

from geonode.layers.models import Layer
from geonode.layers.views import _resolve_layer
from geonode.geoserver.helpers import ogc_server_settings

from .models import LayerStats


def addLayerJSON(request, layertitle):
        """
        Generate a dict that can be serialized to a GXP layer configuration
        suitable for loading this layer.

        The "source" property will be left unset; the layer is not aware of the
        name assigned to its source plugin.  See
        :method:`geonode.maps.models.Map.viewer_json` for an example of
        generating a full map configuration.
        """
        layer = _resolve_layer(request, layertitle)
        cfg = dict()
        cfg['name'] = layer.typename
        cfg['title'] = layer.title
        cfg['transparent'] = True
        if layer.category:
            cfg['group'] = layer.category.identifier
        else:
            cfg['group'] = 'General'
        cfg['url'] = ogc_server_settings.public_url + 'wms'
        cfg['srs'] = layer.srid
        cfg['bbox'] = json.loads("[%s, %s, %s, %s]" % (layer.bbox_x0, layer.bbox_y0,
                                                       layer.bbox_x1, layer.bbox_y1))
        cfg['llbbox'] = json.loads("[%s, %s, %s, %s]" % (layer.bbox_x0, layer.bbox_y0,
                                                         layer.bbox_x1, layer.bbox_y1))
        cfg['queryable'] = (layer.storeType == 'dataStore')
        # cfg['attributes'] = layer.layer_attributes()
        cfg['disabled'] = request.user is not None and not request.user.has_perm(
            'base.view_resourcebase', obj=layer.get_self_resource())
        cfg['visibility'] = True
        cfg['abstract'] = layer.abstract
        cfg['styles'] = ''
        return HttpResponse(json.dumps({'layer': cfg}))


def ajax_increment_layer_stats(request):
    if request.method != 'POST':
        return HttpResponse(
            content='ajax user lookup requires HTTP POST',
            status=405,
            mimetype='text/plain'
        )
    if request.POST['layername'] != '':
        layer_match = Layer.objects.filter(typename=request.POST['layername'])[:1]
        for l in layer_match:
            layerStats,created = LayerStats.objects.get_or_create(layer=l)
            layerStats.visits += 1
            first_visit = True
            if request.session.get('visitlayer' + str(l.id), False):
                first_visit = False
            else:
                request.session['visitlayer' + str(l.id)] = True
            if first_visit or created:
                layerStats.uniques += 1
            layerStats.save()

    return HttpResponse(
                            status=200
    )
