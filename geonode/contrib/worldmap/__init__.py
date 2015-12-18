from django.conf import settings

from geonode.geoserver.helpers import ogc_server_settings
from geonode.maps.models import Map
from geonode.utils import _get_viewer_projection_info


def viewer_json(self, user=None, *added_layers):
        """
        Convert this map to a nested dictionary structure matching the JSON
        configuration for GXP Viewers.

        The ``added_layers`` parameter list allows a list of extra MapLayer
        instances to append to the Map's layer list when generating the
        configuration. These are not persisted; if you want to add layers you
        should use ``.layer_set.create()``.
        """
        layers = list(self.maplayers) + list(added_layers) #implicitly sorted by stack_order

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
                'introtext' : self.content,
                'officialurl' : self.officialurl
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
