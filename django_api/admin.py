from django.contrib import admin

from django_api.models import Circuit, Driver, Race, Result, Team, User


admin.site.register(User)
admin.site.register(Driver)
admin.site.register(Team)
admin.site.register(Circuit)
admin.site.register(Race)
admin.site.register(Result)

