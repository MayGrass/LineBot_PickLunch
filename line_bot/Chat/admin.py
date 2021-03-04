from django.contrib import admin
from django.apps import apps

models = apps.get_models()
# Register your models here.
for model in models:
    try:
        admin.site.register(model)
    except:
        continue
