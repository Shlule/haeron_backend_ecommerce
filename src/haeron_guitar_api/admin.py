from django.contrib import admin
from .models import EngravingTemplate, PartEngravingMark
 
 
@admin.register(EngravingTemplate)
class EngravingTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "mark_type", "part_model", "location", "lightburn_project_path")
    list_filter = ("mark_type", "part_model")
    search_fields = ("name", "location")
 
 
@admin.register(PartEngravingMark)
class PartEngravingMarkAdmin(admin.ModelAdmin):
    list_display = ("part", "mark_type", "value", "location", "status", "template", "confirmed_at", "created_at")
    list_filter = ("status", "mark_type", "template")
    search_fields = ("part__serial_number", "value")
    readonly_fields = ("created_at", "confirmed_at")
    raw_id_fields = ("part",)
 
