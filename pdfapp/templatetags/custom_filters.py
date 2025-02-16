from django import template
from pdfapp.models import VehiclePass, GovVehiclePass

register = template.Library()

@register.filter
def pass_type(pass_obj):
    """Determine if the pass is Private or Government"""
    if isinstance(pass_obj, GovVehiclePass):
        return "Government"
    elif isinstance(pass_obj, VehiclePass):
        return "Private"
    return "Unknown"
