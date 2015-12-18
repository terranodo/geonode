import json

from django.http import HttpResponse

from geonode.layers.models import Layer
from geonode.layers.views import _resolve_layer
from geonode.geoserver.helpers import ogc_server_settings
from geonode.utils import default_map_config

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


def newmap_config(request):
    '''
    View that creates a new map.

    If the query argument 'copy' is given, the inital map is
    a copy of the map with the id specified, otherwise the
    default map configuration is used.  If copy is specified
    and the map specified does not exist a 404 is returned.
    '''
    DEFAULT_MAP_CONFIG, DEFAULT_BASE_LAYERS = default_map_config()

    if request.method == 'GET' and 'copy' in request.GET:
        mapid = request.GET['copy']
        map_obj = get_object_or_404(Map,pk=mapid)

        if not request.user.has_perm('maps.view_map', obj=map_obj):
            return HttpResponse(loader.render_to_string('401.html',
                RequestContext(request, {'error_message':
                    _("You are not permitted to view or copy this map.")})), status=401)

        map_obj.abstract = DEFAULT_ABSTRACT
        map_obj.title = DEFAULT_TITLE
        map_obj.urlsuffix = DEFAULT_URL
        if request.user.is_authenticated(): map_obj.owner = request.user
        config = map_obj.viewer_json(request.user)
        config['edit_map'] = True
        if 'id' in config:
            del config['id']
    else:
        if request.method == 'GET':
            params = request.GET
        elif request.method == 'POST':
            params = request.POST
        else:
            return HttpResponse(status=405)

        if 'layer' in params:
            map_obj = Map(projection="EPSG:900913")
            layers, groups, bbox = additional_layers(request,map_obj, params.getlist('layer'))

            #print 'layers', layers
            #print 'type: ', type(layers[0])
            if bbox is not None:
                minx, miny, maxx, maxy = [float(c) for c in bbox]
                x = (minx + maxx) / 2
                y = (miny + maxy) / 2

                center = forward_mercator((x, y))
                if center[1] == float('-inf'):
                    center[1] = 0

                if maxx == minx:
                    width_zoom = 15
                else:
                    width_zoom = math.log(360 / (maxx - minx), 2)
                if maxy == miny:
                    height_zoom = 15
                else:
                    height_zoom = math.log(360 / (maxy - miny), 2)

                map_obj.center_x = center[0]
                map_obj.center_y = center[1]
                map_obj.zoom = math.ceil(min(width_zoom, height_zoom))

            config = map_obj.viewer_json(request.user, *(DEFAULT_BASE_LAYERS + layers))
            config['map']['groups'] = []
            for group in groups:             
                if group not in json.dumps(config['map']['groups']):
                    config['map']['groups'].append({"expanded":"true", "group":group})

            config['fromLayer'] = True
        else:
            config = DEFAULT_MAP_CONFIG
        config['topic_categories'] = category_list()
        config['edit_map'] = True
    return json.dumps(config)


def new_map(request, template='maps/map_view.html'):
    config = newmap_config(request)
    if isinstance(config, HttpResponse):
        return config
    else:
        return render_to_response(template, RequestContext(request, {
            'config': config,
        }))
