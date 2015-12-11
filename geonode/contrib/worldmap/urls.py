from django.conf.urls import patterns, url

urlpatterns = patterns('geonode.contrib.worldmap.views',
                       url(r'^addgeonodelayer/(?P<layertitle>[^/]*)$', 'addLayerJSON', name="addLayerJSON"),
                       )
