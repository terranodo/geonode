
DEFAULT_LAYER_SOURCE = {
    "ptype": "gxp_gnsource",
    "url": "http://localhost:8080/geoserver/wms",
    "restUrl": "/gs/rest"
}

MAP_BASELAYERS = [
 {
        "source": {"ptype": "gx_olsource"},
        "type": "OpenLayers.Layer",
        "args": ["No background"],
        "visibility": False,
        "fixed": True,
        "group": "background"
    }, {
        "source": {"ptype": "gx_olsource"},
        "type": "OpenLayers.Layer.OSM",
        "args": ["OpenStreetMap"],
        "visibility": False,
        "fixed": True,
        "group": "background"
    }, {
        "source": {"ptype": "gxp_mapquestsource"},
        "name": "osm",
        "group": "background",
        "visibility": True
    }, {
        "source": {"ptype": "gxp_mapquestsource"},
        "name": "naip",
        "group": "background",
        "visibility": False
    }, {
        "source": {"ptype": "gxp_mapboxsource"},
    }, {
        "source": {"ptype": "gx_googlesource"},
        "group": "background",
        "name": "SATELLITE",
        "visibility": False,
        "fixed": True,
    }, {
        "source": {"ptype": "gx_googlesource"},
        "group": "background",
        "name": "TERRAIN",
        "visibility": False,
        "fixed": True,
    }, {
        "source": {"ptype": "gx_googlesource"},
        "group": "background",
        "name": "HYBRID",
        "visibility": False,
        "fixed": True,
    }, {
        "source": {"ptype": "gx_googlesource"},
        "group": "background",
        "name": "ROADMAP",
        "visibility": False,
        "fixed": True,
        "group": "background"
    }, {
        "source": DEFAULT_LAYER_SOURCE
    }
]


GEONODE_CLIENT_LOCATION = "http://localhost:9090/"
# GEONODE_CLIENT_LOCATION = "/static/worldmap/build/app/static/"

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    "django.core.context_processors.tz",
    'django.core.context_processors.media',
    "django.core.context_processors.static",
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
    'account.context_processors.account',
    # The context processor below adds things like SITEURL
    # and GEOSERVER_BASE_URL to all pages that use a RequestContext
    'geonode.context_processors.resource_urls',
    'geonode.geoserver.context_processors.geoserver_urls',
    'geonode.contrib.worldmap.context_processors.worldmap_urls'
)
