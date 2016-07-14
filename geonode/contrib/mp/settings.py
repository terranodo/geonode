from django.conf import settings

# make geonode mapping clients to use tiles directly from the disk
# REQURES WEB SERVER CONFIGURATION TO SERVE FILE_CACHE_DIRECTORY
USE_DISK_CACHE = getattr(settings, 'USE_DISK_CACHE', False)

# create mapproxy cache for all geonode layers
USE_DJMP_FOR_ALL_LAYERS = getattr(settings, 'USE_DJMP_FOR_ALL_LAYERS', False)
