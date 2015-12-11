import settings


def worldmap_urls(request):
    """Global values to pass to templates"""
    defaults = dict(
        GEONODE_CLIENT_LOCATION=settings.GEONODE_CLIENT_LOCATION
    )

    return defaults
