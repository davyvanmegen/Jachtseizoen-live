from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("g/<str:code>/lobby/", views.lobby, name="lobby"),
    path("g/<str:code>/", views.game_view, name="game"),
    path("g/<str:code>/settings/", views.update_settings, name="update_settings"),
    path("g/<str:code>/start/", views.start_game, name="start_game"),
    path("g/<str:code>/stop/", views.stop_game, name="stop_game"),
    path("g/<str:code>/location/", views.location_ping, name="location_ping"),
    path("g/<str:code>/caught/", views.mark_caught, name="mark_caught"),
    path("g/<str:code>/state/", views.state, name="state"),
    path("g/<str:code>/snapshots/", views.snapshots, name="snapshots"),
]
