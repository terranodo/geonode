from django.core.management.base import BaseCommand
from optparse import make_option

from geonode.contrib.dynamic.models import configure_models
from geonode.layers.models import Layer


class Command(BaseCommand):
    help = ("Make the specified layers enabled to feature level spatial search")

    args = 'layers [layer1,layers,...]'

    option_list = BaseCommand.option_list + (
        make_option(
            '-l',
            '--layers',
            dest="layers",
            default=None,
            help="Layer typenames"),
    )

    def handle(self, *args, **options):
        layers = options.get('layers')
        
        for typename in layers.split(','):
            try:
                layer_obj = Layer.objects.get(typename=typename)
                configure_models(layer_obj, Layer)
                print 'Layer %s enabled for feature level spatial search' % typename

            except Layer.DoesNotExist:
                print "Couldn't find layer %s" % typename
