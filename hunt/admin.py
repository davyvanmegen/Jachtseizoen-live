from django.contrib import admin

from .models import Game, LocationPing, Player, ReleasedLocationSnapshot


admin.site.register(Game)
admin.site.register(Player)
admin.site.register(LocationPing)
admin.site.register(ReleasedLocationSnapshot)
