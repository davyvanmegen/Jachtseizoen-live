import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .forms import CreateGameForm, HostSettingsForm, JoinGameForm
from .models import Game, LocationPing, Player
from .services import game_payload, latest_snapshots_for_game, snapshot_payload


def session_key(game):
    return f"game_{game.id}_player_id"


def player_url(game, player, view_name):
    url = reverse(view_name, args=[game.code])
    return f"{url}?player_id={player.id}&token={player.access_token}"


def current_player(request, game):
    token_player_id = request.headers.get("X-Player-Id") or request.GET.get("player_id")
    token = request.headers.get("X-Player-Token") or request.GET.get("token")
    if token_player_id and token:
        player = Player.objects.filter(game=game, id=token_player_id, access_token=token).first()
        if player:
            request.session[session_key(game)] = player.id
            return player

    player_id = request.session.get(session_key(game))
    if not player_id:
        return None
    return Player.objects.filter(game=game, id=player_id).first()


def broadcast_game(game):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"game_{game.code}",
        {"type": "game.update", "payload": game_payload(game, include_snapshots=True)},
    )


def wants_json(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def forbidden_response(request, message):
    if wants_json(request):
        return JsonResponse({"error": message}, status=403)
    raise PermissionDenied(message)


@ensure_csrf_cookie
def home(request):
    create_form = CreateGameForm(prefix="create")
    join_form = JoinGameForm(prefix="join")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            create_form = CreateGameForm(request.POST, prefix="create")
            if create_form.is_valid():
                game = Game.objects.create(code=Game.generate_code())
                player = Player.objects.create(game=game, name=create_form.cleaned_data["name"], is_host=True)
                request.session[session_key(game)] = player.id
                return redirect(player_url(game, player, "lobby"))
        elif action == "join":
            join_form = JoinGameForm(request.POST, prefix="join")
            if join_form.is_valid():
                game = get_object_or_404(Game, code=join_form.cleaned_data["code"])
                if game.status != Game.Status.LOBBY:
                    messages.error(request, "Deze game is al gestart.")
                else:
                    player = Player.objects.create(game=game, name=join_form.cleaned_data["name"])
                    request.session[session_key(game)] = player.id
                    broadcast_game(game)
                    return redirect(player_url(game, player, "lobby"))
    return render(request, "hunt/home.html", {"create_form": create_form, "join_form": join_form})


@ensure_csrf_cookie
def lobby(request, code):
    game = get_object_or_404(Game.objects.prefetch_related("players"), code=code)
    player = current_player(request, game)
    if not player:
        return redirect("home")
    if game.status != Game.Status.LOBBY:
        return redirect(player_url(game, player, "game"))
    return render(request, "hunt/lobby.html", {"game": game, "player": player})


@ensure_csrf_cookie
def game_view(request, code):
    game = get_object_or_404(Game.objects.prefetch_related("players"), code=code)
    player = current_player(request, game)
    if not player:
        return redirect("home")
    game.release_snapshot_if_due()
    if game.status == Game.Status.LOBBY:
        return redirect(player_url(game, player, "lobby"))
    return render(request, "hunt/game.html", {"game": game, "player": player})


def require_player(request, code):
    game = get_object_or_404(Game.objects.prefetch_related("players"), code=code)
    player = current_player(request, game)
    if not player:
        raise PermissionDenied("Je zit niet in deze game.")
    return game, player


@require_POST
def update_settings(request, code):
    game, player = require_player(request, code)
    if not player.is_host:
        return forbidden_response(request, "Alleen de host mag instellingen wijzigen.")
    if game.status != Game.Status.LOBBY:
        return JsonResponse({"error": "Instellingen kunnen alleen in de lobby wijzigen."}, status=400)

    form = HostSettingsForm(request.POST, instance=game)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    form.save()
    Player.objects.filter(game=game).update(is_start_runner=False)
    try:
        selected = form.selected_players(game)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    selected.update(is_start_runner=True)
    broadcast_game(game)
    return JsonResponse(game_payload(game, player))


@require_POST
def start_game(request, code):
    game, player = require_player(request, code)
    if not player.is_host:
        return forbidden_response(request, "Alleen de host mag starten.")
    expects_json = wants_json(request)
    try:
        game.start()
    except ValidationError as exc:
        if not expects_json:
            messages.error(request, "; ".join(exc.messages))
            return redirect("lobby", code=game.code)
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    broadcast_game(game)
    if not expects_json:
        return redirect(player_url(game, player, "game"))
    return JsonResponse({"redirect": player_url(game, player, "game")})


@require_POST
def stop_game(request, code):
    game, player = require_player(request, code)
    if not player.is_host:
        return forbidden_response(request, "Alleen de host mag het spel stoppen.")
    game.return_to_lobby()
    broadcast_game(game)
    if not wants_json(request):
        return redirect(player_url(game, player, "lobby"))
    return JsonResponse({"redirect": player_url(game, player, "lobby")})


@require_POST
def location_ping(request, code):
    game, player = require_player(request, code)
    if game.status not in (Game.Status.GRACE, Game.Status.ACTIVE):
        return JsonResponse({"ok": False, "ignored": True})
    try:
        data = json.loads(request.body.decode("utf-8"))
        lat = float(data["latitude"])
        lon = float(data["longitude"])
        accuracy = data.get("accuracy")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Ongeldige locatie."}, status=400)
    LocationPing.objects.create(
        game=game,
        player=player,
        latitude=lat,
        longitude=lon,
        accuracy=float(accuracy) if accuracy is not None else None,
    )
    released = game.release_snapshot_if_due()
    if released:
        broadcast_game(game)
    return JsonResponse({"ok": True})


@require_POST
def mark_caught(request, code):
    game, player = require_player(request, code)
    if game.status not in (Game.Status.GRACE, Game.Status.ACTIVE):
        return JsonResponse({"error": "Je kunt dit nu niet doen."}, status=400)
    try:
        player.mark_caught()
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    broadcast_game(game)
    return JsonResponse(game_payload(game, player, include_snapshots=True))


def state(request, code):
    game, player = require_player(request, code)
    released = game.release_snapshot_if_due()
    if released:
        broadcast_game(game)
    include = player.role == Player.Role.HUNTER or game.status == Game.Status.FINISHED
    payload = game_payload(game, player, include_snapshots=include)
    if not include:
        payload["snapshots"] = []
    return JsonResponse(payload)


def snapshots(request, code):
    game, player = require_player(request, code)
    if player.role != Player.Role.HUNTER and game.status != Game.Status.FINISHED:
        raise Http404
    game.release_snapshot_if_due()
    return JsonResponse({"snapshots": [snapshot_payload(s) for s in latest_snapshots_for_game(game)]})
