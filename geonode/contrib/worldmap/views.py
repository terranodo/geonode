import json
import logging
import uuid
import math

from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils.html import escape
from django.db.models import signals
from django.core.urlresolvers import reverse

from geoserver.catalog import Catalog

from geonode import GeoNodeException
from geonode.layers.models import Layer
from geonode.layers.views import _resolve_layer
from geonode.geoserver.helpers import ogc_server_settings, _user, _password, get_sld_for
from geonode.geoserver.signals import geoserver_pre_save
from geonode.utils import default_map_config, llbbox_to_mercator, forward_mercator
from geonode.base.models import TopicCategory
from geonode.layers.utils import get_valid_layer_name
from geonode.people.models import Profile
from geonode.maps.models import Map, MapLayer

from .models import LayerStats
from .forms import LayerCreateForm, GEOMETRY_CHOICES

logger = logging.getLogger("geonode.contrib.worldmap")

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

    If the query argument 'copy' is given, the initial map is
    a copy of the map with the id specified, otherwise the
    default map configuration is used.  If copy is specified
    and the map specified does not exist a 404 is returned.
    '''
    DEFAULT_MAP_CONFIG, DEFAULT_BASE_LAYERS = default_map_config()

    if request.method == 'GET' and 'copy' in request.GET:
        mapid = request.GET['copy']
        map_obj = _resolve_map(request, mapid, 'base.view_resourcebase')

        map_obj.abstract = DEFAULT_ABSTRACT
        map_obj.title = DEFAULT_TITLE
        if request.user.is_authenticated():
            map_obj.owner = request.user
        config = map_obj.viewer_json(request.user)
        del config['id']
    else:
        if request.method == 'GET':
            params = request.GET
        elif request.method == 'POST':
            params = request.POST
        else:
            return HttpResponse(status=405)

        if 'layer' in params:
            bbox = None
            map_obj = Map(projection=getattr(settings, 'DEFAULT_MAP_CRS',
                          'EPSG:900913'))
            layers = []
            for layer_name in params.getlist('layer'):
                try:
                    layer = _resolve_layer(request, layer_name)
                except ObjectDoesNotExist:
                    # bad layer, skip
                    continue

                if not request.user.has_perm(
                        'view_resourcebase',
                        obj=layer.get_self_resource()):
                    # invisible layer, skip inclusion
                    continue

                layer_bbox = layer.bbox
                # assert False, str(layer_bbox)
                if bbox is None:
                    bbox = list(layer_bbox[0:4])
                else:
                    bbox[0] = min(bbox[0], layer_bbox[0])
                    bbox[1] = max(bbox[1], layer_bbox[1])
                    bbox[2] = min(bbox[2], layer_bbox[2])
                    bbox[3] = max(bbox[3], layer_bbox[3])

                config = layer.attribute_config()

                # Add required parameters for GXP lazy-loading
                config["title"] = layer.title
                config["queryable"] = True

                config["srs"] = getattr(settings, 'DEFAULT_MAP_CRS', 'EPSG:900913')
                config["bbox"] = bbox if config["srs"] != 'EPSG:900913' \
                    else llbbox_to_mercator([float(coord) for coord in bbox])

                if layer.storeType == "remoteStore":
                    service = layer.service
                    maplayer = MapLayer(map=map_obj,
                                        name=layer.typename,
                                        ows_url=layer.ows_url,
                                        layer_params=json.dumps(config),
                                        visibility=True,
                                        source_params=json.dumps({
                                            "ptype": service.ptype,
                                            "remote": True,
                                            "url": service.base_url,
                                            "name": service.name}))
                else:
                    maplayer = MapLayer(
                        map=map_obj,
                        name=layer.typename,
                        ows_url=layer.ows_url,
                        layer_params=json.dumps(config),
                        visibility=True
                    )

                layers.append(maplayer)

            if bbox is not None:
                minx, miny, maxx, maxy = [float(c) for c in bbox]
                x = (minx + maxx) / 2
                y = (miny + maxy) / 2

                center = list(forward_mercator((x, y)))
                if center[1] == float('-inf'):
                    center[1] = 0

                BBOX_DIFFERENCE_THRESHOLD = 1e-5

                # Check if the bbox is invalid
                valid_x = (maxx - minx) ** 2 > BBOX_DIFFERENCE_THRESHOLD
                valid_y = (maxy - miny) ** 2 > BBOX_DIFFERENCE_THRESHOLD

                if valid_x:
                    width_zoom = math.log(360 / abs(maxx - minx), 2)
                else:
                    width_zoom = 15

                if valid_y:
                    height_zoom = math.log(360 / abs(maxy - miny), 2)
                else:
                    height_zoom = 15

                map_obj.center_x = center[0]
                map_obj.center_y = center[1]
                map_obj.zoom = math.ceil(min(width_zoom, height_zoom))

            config = map_obj.viewer_json(
                request.user, *(DEFAULT_BASE_LAYERS + layers))
            config['fromLayer'] = True
        else:
            config = DEFAULT_MAP_CONFIG
        config['topic_categories'] = [[t.identifier, t.gn_description] for t in TopicCategory.objects.all()]
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


@login_required
def create_pg_layer(request):
    if request.method == 'GET':
        layer_form = LayerCreateForm(prefix="layer")

        # Determine if this page will be shown in a tabbed panel or full page
        pagetorender = "maps/layer_create_tab.html" if "tab" in request.GET else "maps/layer_create.html"


        return render_to_response(pagetorender, RequestContext(request, {
            "layer_form": layer_form,
            "customGroup": settings.CUSTOM_GROUP_NAME if settings.USE_CUSTOM_ORG_AUTHORIZATION else '',
            "geoms": GEOMETRY_CHOICES
        }))

    if request.method == 'POST':
        from collections import OrderedDict

        # Disconnect the geoserver pre save signal
        signals.pre_save.disconnect(geoserver_pre_save, sender=Layer)

        layer_form = LayerCreateForm(request.POST)
        if layer_form.is_valid():
            cat = Catalog(ogc_server_settings.internal_rest, _user, _password)

            # Assume default workspace
            ws = cat.get_workspace(settings.DEFAULT_WORKSPACE)
            if ws is None:
                msg = 'Specified workspace [%s] not found' % settings.DEFAULT_WORKSPACE
                return HttpResponse(msg, status='400')

            # Assume datastore used for PostGIS
            store = ogc_server_settings.server['DATASTORE']
            if store is None:
                msg = 'Specified store [%s] not found' % ogc_server_settings.server['DATASTORE']
                return HttpResponse(msg, status='400')

            #TODO: Let users create their own schema
            attribute_list = [
                ["the_geom","com.vividsolutions.jts.geom." + layer_form.cleaned_data['geom'],{"nillable":False}],
                ["Name","java.lang.String",{"nillable":True}],
                ["Description","java.lang.String", {"nillable":True}],
                ["Start_Date","java.util.Date",{"nillable":True}],
                ["End_Date","java.util.Date",{"nillable":True}],
                ["String_Value_1","java.lang.String",{"nillable":True}],
                ["String_Value_2","java.lang.String", {"nillable":True}],
                ["Number_Value_1","java.lang.Float",{"nillable":True}],
                ["Number_Value_2","java.lang.Float", {"nillable":True}],
            ]

            # Add geometry to attributes dictionary, based on user input; use OrderedDict to remember order
            #attribute_list.insert(0,[u"the_geom",u"com.vividsolutions.jts.geom." + layer_form.cleaned_data['geom'],{"nillable":False}])

            name = get_valid_layer_name(layer_form.cleaned_data['name'], False)
            permissions = layer_form.cleaned_data["permissions"]

            try:
                logger.info("Create layer %s", name)
                layer = cat.create_native_layer(settings.DEFAULT_WORKSPACE,
                                          ogc_server_settings.server['DATASTORE'],
                                          name,
                                          name,
                                          escape(layer_form.cleaned_data['title']),
                                          layer_form.cleaned_data['srs'],
                                          attribute_list)

                logger.info("Create default style")
                publishing = cat.get_layer(name)
                sld = get_sld_for(publishing)
                cat.create_style(name, sld)
                publishing.default_style = cat.get_style(name)
                cat.save(publishing)

                logger.info("Check projection")
                check_projection(name, layer)

                logger.info("Create django record")
                geonodeLayer = create_django_record(request.user, layer_form.cleaned_data['title'], layer_form.cleaned_data['keywords'].strip().split(" "), layer_form.cleaned_data['abstract'], layer, permissions)


                # Reconnect the geoserver pre save signal
                signals.pre_save.connect(geoserver_pre_save, sender=Layer)

                redirect_to  = reverse('layer_metadata', args=[geonodeLayer.typename])
                if 'mapid' in request.POST and request.POST['mapid'] == 'tab': #if mapid = tab then open metadata form in tabbed panel
                    redirect_to+= "?tab=worldmap_create_panel"
                elif 'mapid' in request.POST and request.POST['mapid'] != '': #if mapid = number then add to parameters and open in full page
                    redirect_to += "?map=" + request.POST['mapid']
                return HttpResponse(json.dumps({
                    "success": True,
                    "redirect_to": redirect_to}))
            except Exception, e:
                logger.exception("Unexpected error.")
                return HttpResponse(json.dumps({
                    "success": False,
                    "errors": ["Unexpected error: " + escape(str(e))]}))

        else:
            #The form has errors, what are they?
            return HttpResponse(layer_form.errors, status='500')


def check_projection(name, resource):
    # Get a short handle to the gsconfig geoserver catalog
    cat = Catalog(ogc_server_settings.internal_rest, _user, _password)

    try:
        if resource.latlon_bbox is None:
            box = resource.native_bbox[:4]
            minx, maxx, miny, maxy = [float(a) for a in box]
            if -180 <= minx <= 180 and -180 <= maxx <= 180 and\
               -90  <= miny <= 90  and -90  <= maxy <= 90:
                logger.warn('GeoServer failed to detect the projection for layer '
                            '[%s]. Guessing EPSG:4326', name)
                # If GeoServer couldn't figure out the projection, we just
                # assume it's lat/lon to avoid a bad GeoServer configuration

                resource.latlon_bbox = resource.native_bbox
                resource.projection = "EPSG:4326"
                cat.save(resource)
            else:
                msg = ((_('GeoServer failed to detect the projection for layer ') + 
                       '[%s].' + 
                       _('It doesn\'t look like EPSG:4326, so backing out the layer.')))
                logger.warn(msg, name)
                cascading_delete(cat, resource)
                raise GeoNodeException(msg % name)
    except:
        msg = ((_('GeoServer failed to read the layer projection for') + ' [%s] ' + 
               _('so backing out the layer.')))
        cascading_delete(cat, resource)
        raise GeoNodeException(msg % name)


def create_django_record(user, title, keywords, abstract, gs_resource, permissions):
    name = gs_resource.name
    typename = gs_resource.store.workspace.name + ':' + name
    layer_uuid = str(uuid.uuid1())
    defaults = dict(store=gs_resource.store.name,
                    storeType=gs_resource.store.resource_type,
                    typename=typename,
                    title=title or gs_resource.title,
                    uuid=layer_uuid,
                    abstract=abstract or gs_resource.abstract or '',
                    owner=user)
    saved_layer, created = Layer.objects.get_or_create(name=gs_resource.name,
                                                       workspace=gs_resource.store.workspace.name,
                                                       defaults=defaults)

    if created:
        saved_layer.set_default_permissions()
        saved_layer.keywords.add(*keywords)

    try:
        # Step 9. Delete layer attributes if they no longer exist in an updated layer
        logger.info('>>> Step 11. Delete layer attributes if they no longer exist in an updated layer [%s]', name)
        attributes = LayerAttribute.objects.filter(layer=saved_layer)
        attrNames = saved_layer.attribute_names
        if attrNames is not None:
            for la in attributes:
                lafound = False
                for field, ftype in attrNames.iteritems():
                    if field == la.attribute:
                        lafound = True
                if not lafound:
                    logger.debug("Going to delete [%s] for [%s]", la.attribute, saved_layer.name)
                    la.delete()

        #
        # Step 10. Add new layer attributes if they dont already exist
        logger.info('>>> Step 10. Add new layer attributes if they dont already exist in an updated layer [%s]', name)
        if attrNames is not None:
            logger.debug("Attributes are not None")
            iter = 1
            mark_searchable = True
            for field, ftype in attrNames.iteritems():
                    if field is not None and  ftype.find("gml:") != 0:
                        las = LayerAttribute.objects.filter(layer=saved_layer, attribute=field)
                        if len(las) == 0:
                            la = LayerAttribute.objects.create(layer=saved_layer, attribute=field, attribute_label=field.title(), attribute_type=ftype, searchable=(ftype == "xsd:string" and mark_searchable), display_order = iter)
                            la.save()
                            if la.searchable:
                                mark_searchable = False
                            iter+=1
        else:
            logger.debug("No attributes found")

    except Exception, ex:
                    logger.debug("Attributes could not be saved:[%s]", str(ex))

    poc_contact = user
    author_contact = user

    logger.debug('Creating poc and author records for %s', poc_contact)

    saved_layer.poc = poc_contact
    saved_layer.metadata_author = author_contact

    ## TODO, What to do here?
    #saved_layer.save_to_geonetwork()

    # Step 11. Set default permissions on the newly created layer
    # FIXME: Do this as part of the post_save hook
    logger.info('>>> Step 11. Setting default permissions for [%s]', name)
    if permissions is not None:
        saved_layer.set_permissions(permissions)

    # Step 12. Verify the layer was saved correctly and clean up if needed
    logger.info('>>> Step 12. Verifying the layer [%s] was created '
                'correctly' % name)

    # Verify the object was saved to the Django database
    try:
        Layer.objects.get(name=name)
    except Layer.DoesNotExist, e:
        msg = ((_('There was a problem saving the layer ') + '%s ' +
               _('Error is: ') + '%s') % (name, str(e)))
        logger.exception(msg)
        logger.debug('Attempting to clean up after failed save for layer '
                     '[%s]', name)
        # Since the layer creation was not successful, we need to clean up
        cleanup(name, layer_uuid)
        raise GeoNodeException(msg)

    # Verify it is correctly linked to GeoServer and GeoNetwork
    try:
        # FIXME: Implement a verify method that makes sure it was
        # saved in both GeoNetwork and GeoServer
        saved_layer.verify()
    except AttributeError, e:
        logger.exception('>>> FIXME: Please, if you can write python code, '
                         'implement "verify()" '
                         'method in geonode.maps.models.Layer')
    except GeoNodeException, e:
        msg = (_('The layer was not correctly saved to '
               'GeoNetwork/GeoServer. Error is: ') + str(e))
        logger.exception(msg)
        e.args = (msg,)
        # Deleting the layer
        saved_layer.delete()
        raise

    # Return the created layer object
    return saved_layer

