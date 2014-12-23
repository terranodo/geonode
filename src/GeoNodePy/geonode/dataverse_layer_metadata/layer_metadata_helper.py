from __future__ import print_function
import logging

from django import forms
from geonode.dataverse_layer_metadata.models import DataverseLayerMetadata
from geonode.dataverse_layer_metadata.forms import DataverseLayerMetadataValidationForm

from geonode.maps.models import Layer

logger = logging.getLogger("geonode.dataverse_layer_metadata.layer_metadata_helper")


def check_for_existing_layer(dataverse_info):
    """
    Using the dataverse_info information

    Does the datafile_id in dataverse_info match an existing DataverseLayerMetadata object?

    Yes:  return first matching DataverseLayerMetadata object
    No: return None
    """
    assert type(dataverse_info) is dict, "dataverse_info must be type dict. Found type: %s" % type(dataverse_info)

    # Validate the data
    f = DataverseLayerMetadataValidationForm(dataverse_info)
    if not f.is_valid():
        logger.error('check_for_existing_layer. failed validation')
        logger.error('Errors: %s' % f.errors)
        raise forms.ValidationError('Failed to validate dataverse_info data')

    # Check for DataverseLayerMetadata objects with the same "datafile_id"
    l = DataverseLayerMetadata.objects.filter(datafile_id=f.cleaned_data.get('datafile_id'))

    # If DataverseLayerMetadata objects match, return the 1st one
    # (Note: Not ~yet~ enforcing only 1 DataverseLayerMetadata per datafile_id.
    #   But will be only making one layer 'in practice'
    #   This is a late date chance where original discussions included multiple layers per file.
    #
    if l.count() > 0:
        return l[0]

    return None


def update_the_layer_metadata(dv_layer_metadata, dataverse_info):

    assert type(dv_layer_metadata) is DataverseLayerMetadata, "dv_layer_metadata must be a DataverseLayerMetadata object.  Found type: %s" % type(dv_layer_metadata)
    assert type(dataverse_info) is dict, "dataverse_info must be type dict. Found type: %s" % type(dataverse_info)

    # Validate the data
    f = DataverseLayerMetadataValidationForm(dataverse_info)
    if not f.is_valid():
        raise forms.ValidationError('Failed to validate dataverse_info data')

    # Update the metadata, field by field
    for k, v in f.cleaned_data.items():
        setattr(dv_layer_metadata, k, v)
        dv_layer_metadata.save()



def add_dataverse_layer_metadata(saved_layer, dataverse_info):
    """
    If a Layer has been created via Dataverse, create a DataverseLayerMetadata object.

    fail: return None
    success: return DataverseLayerMetadata object
    """
    assert type(saved_layer) is Layer, "saved_layer must be type Layer.  Found: %s" % type(Layer)
    assert type(dataverse_info) is dict, "dataverse_info must be type dict. Found type: %s" % type(dataverse_info)

    (success, create_datetime_obj_or_err_str) = DataverseLayerMetadataValidationForm.format_datafile_create_datetime(dataverse_info.get('datafile_create_datetime', None))

    if success is False:
        print ('failed to format datetime', create_datetime_obj_or_err_str)
        logger.error('Invalid "datafile_create_datetime"\n%s' % create_datetime_obj_or_err_str)
        return None

    dataverse_info['datafile_create_datetime'] = create_datetime_obj_or_err_str

    f = DataverseLayerMetadataValidationForm(dataverse_info)
    #print (dir(f))
    if not f.is_valid():
        print ('failed validation')
        print (f.errors)
        logger.error("Unexpected form validation error in add_dataverse_layer_metadata. dvn import: %s" % f.errors)
        return None


    # Create the DataverseLayerMetadata object
    layer_metadata = f.save(commit=False)


    # Add the related Layer object
    layer_metadata.map_layer = saved_layer

    # Save it!!
    layer_metadata.save()
    
    return layer_metadata
    
