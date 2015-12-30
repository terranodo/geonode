import json

from django.conf import settings

from geonode.geoserver.helpers import ogc_server_settings
from geonode.maps.models import Map
from geonode.utils import _get_viewer_projection_info

from geoserver.catalog import Catalog


class ConflictingDataError(Exception):
    pass


def viewer_json(self, user=None, *added_layers):
        """
        Convert this map to a nested dictionary structure matching the JSON
        configuration for GXP Viewers.

        The ``added_layers`` parameter list allows a list of extra MapLayer
        instances to append to the Map's layer list when generating the
        configuration. These are not persisted; if you want to add layers you
        should use ``.layer_set.create()``.
        """
        layers = list(self.layers) + list(added_layers) #implicitly sorted by stack_order

        sejumps = self.jump_set.all()
        server_lookup = {}
        sources = {'local': settings.DEFAULT_LAYER_SOURCE }

        def uniqify(seq):
            """
            get a list of unique items from the input sequence.

            This relies only on equality tests, so you can use it on most
            things.  If you have a sequence of hashables, list(set(seq)) is
            better.
            """
            results = []
            for x in seq:
                if x not in results: results.append(x)
            return results


        def uniqifydict(seq, item):
            """
            get a list of unique dictionary elements based on a certain  item (ie 'group').
            """
            results = []
            items = []
            for x in seq:
                if x[item] not in items:
                    items.append(x[item])
                    results.append(x)
            return results

        configs = [l.source_config() for l in layers]
        configs.append({"ptype":"gxp_gnsource", "url": ogc_server_settings.public_url + "wms", "restUrl":"/gs/rest"})

        i = 0
        for source in uniqify(configs):
            while str(i) in sources: i = i + 1
            sources[str(i)] = source
            server_lookup[json.dumps(source)] = str(i)

        def source_lookup(source):
            for k, v in sources.iteritems():
                if v == source: return k
            return None

        def layer_config(l, user):
            cfg = l.layer_config(user)
            src_cfg = l.source_config()
            source = source_lookup(src_cfg)
            if source: cfg["source"] = source
            if src_cfg.get("ptype", "gxp_wmscsource") == "gxp_wmscsource"  or src_cfg.get("ptype", "gxp_gnsource") == "gxp_gnsource" : cfg["buffer"] = 0
            return cfg

        config = {
            'id': self.id,
            'about': {
                'title':   self.title,
                'abstract': self.abstract,
                'urlsuffix': self.urlsuffix,
                'officialurl' : self.distribution_url
            },
            'defaultSourceType': "gxp_gnsource",
            'sources': sources,
            'map': {
                'layers': [layer_config(l, user) for l in layers],
                'center': [self.center_x, self.center_y],
                'projection': self.projection,
                'zoom': self.zoom,

                },
            'social_explorer': [se.json() for se in sejumps]
        }


        if self.group_params:
            #config["treeconfig"] = json.loads(self.group_params)
            config["map"]["groups"] = uniqifydict(json.loads(self.group_params), 'group')

        '''
        # Mark the last added layer as selected - important for data page
        '''
        config["map"]["layers"][len(layers)-1]["selected"] = True

        config["map"].update(_get_viewer_projection_info(self.projection))

        return config

Map.viewer_json = viewer_json


def create_native_layer(self, workspace, store, name,
          native_name, title, srs, attributes):
    """
    Physically create a layer in one of GeoServer's datastores.
    For example, this will actually create a table in a Postgis store.

    Parameters include:
    workspace - the Workspace object or name of the workspace of the store to
       use
    store - the Datastore object or name of the store to use
    name - the published name of the store
    native_name - the name used in the native storage format (such as a
        filename or database table name)
    title - the title for the created featuretype configuration
    srs - the SRID for the SRS to use (like "EPSG:4326" for lon/lat)
    attributes - a dict specifying the names and types of the attributes for
       the new table.  Types should be specified using Java class names:

       * boolean = java.lang.Boolean
       * byte = java.lang.Byte
       * timestamp = java.util.Date
       * double = java.lang.Double
       * float = java.lang.Float
       * integer = java.lang.Integer
       * long = java.lang.Long
       * short = java.lang.Short
       * string = java.lang.String
    """
    if isinstance(workspace, basestring):
        ws = self.get_workspace(workspace)
    elif workspace is None:
        ws = self.get_default_workspace()
    ds = self.get_store(store, ws)
    existing_layer = self.get_resource(name, ds, ws) 
    if existing_layer is not None:
        msg = "There is already a layer named %s in %s" % (name, workspace)
        raise ConflictingDataError(msg)
    if len(attributes) < 1:
        msg = "The specified attributes are invalid"
        raise InvalidAttributesError(msg)

    has_geom = False
    attributes_block = "<attributes>"
    empty_opts = {}
    for spec in attributes:
        if len(spec) == 2:
            att_name, binding = spec
            opts = empty_opts
        elif len(spec) == 3:
            att_name, binding, opts = spec
        else:
            raise InvalidAttributesError("expected tuple of (name,binding,dict?)")

        nillable = opts.get("nillable",False)

        if binding.find("com.vividsolutions.jts.geom") >= 0:
            has_geom = True

        attributes_block += ("<attribute>"
            "<name>{name}</name>"
            "<binding>{binding}</binding>"
            "<nillable>{nillable}</nillable>"
            "</attribute>").format(name=att_name, binding=binding, nillable=nillable)
    attributes_block += "</attributes>"

    if has_geom == False:
        msg = "Geometryless layers are not currently supported"
        raise InvalidAttributesError(msg)

    xml = ("<featureType>"
            "<name>{name}</name>"
            "<nativeName>{native_name}</nativeName>"
            "<title>{title}</title>"
            "<srs>{srs}</srs>"
            "{attributes}"
            "</featureType>").format(name=name.encode('UTF-8','strict'), native_name=native_name.encode('UTF-8','strict'), 
                                        title=title.encode('UTF-8','strict'), srs=srs,
                                        attributes=attributes_block)
    headers = { "Content-Type": "application/xml" }
    url = '%s/workspaces/%s/datastores/%s/featuretypes?charset=UTF-8' % (self.service_url, ws.name, store)
    headers, response = self.http.request(url, "POST", xml, headers)
    assert 200 <= headers.status < 300, "Tried to create PostGIS Layer but got " + str(headers.status) + ": " + response
    self._cache.clear()
    return self.get_resource(name, ds, ws)


Catalog.create_native_layer = create_native_layer
