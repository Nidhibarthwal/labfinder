from django.apps import AppConfig


class SamplesConfigurationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.samples_configurations'

    # def ready(self):
    #     import apps.samples_configurations.signals
