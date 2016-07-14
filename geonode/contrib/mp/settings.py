from django.conf import settings

USE_DISK_CACHE = getattr(settings, 'USE_DISK_CACHE', False)