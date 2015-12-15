import settings

from geonode.geoserver.helpers import ogc_server_settings

def worldmap_urls(request):
    """Global values to pass to templates"""
    defaults = dict(
        GEONODE_CLIENT_LOCATION=settings.GEONODE_CLIENT_LOCATION,
        DB_DATASTORE=True if 'postgis' in ogc_server_settings.datastore_db['ENGINE'] else False
    )

    return defaults
