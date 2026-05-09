from django.utils import timezone

from .models import Game


def next_snapshot_at(game):
    if game.status == Game.Status.GRACE:
        return game.active_at
    if game.status == Game.Status.ACTIVE:
        if game.last_snapshot_released_at:
            return game.last_snapshot_released_at + timezone.timedelta(seconds=game.snapshot_interval_seconds)
        return timezone.now()
    return None


def player_payload(player):
    return {
        "id": player.id,
        "name": player.name,
        "role": player.role,
        "role_label": player.role_label,
        "is_host": player.is_host,
        "is_start_runner": player.is_start_runner,
        "caught_at": player.caught_at.isoformat() if player.caught_at else None,
    }


def latest_snapshots_for_game(game):
    latest = {}
    snapshots = game.released_snapshots.select_related("player").filter(player__role="fugitive")
    for snapshot in snapshots:
        latest.setdefault(snapshot.player_id, snapshot)
    return list(latest.values())


def snapshot_payload(snapshot):
    return {
        "player_id": snapshot.player_id,
        "player_name": snapshot.player.name,
        "latitude": snapshot.latitude,
        "longitude": snapshot.longitude,
        "accuracy": snapshot.accuracy,
        "pinged_at": snapshot.pinged_at.isoformat(),
        "released_at": snapshot.released_at.isoformat(),
    }


def caught_payload(player):
    return {
        "id": player.id,
        "name": player.name,
        "caught_at": player.caught_at.isoformat() if player.caught_at else None,
    }


def game_payload(game, current_player=None, include_snapshots=False):
    game.update_status_from_time()
    game.finish_if_no_fugitives()
    next_release = next_snapshot_at(game)
    payload = {
        "code": game.code,
        "status": game.status,
        "server_time": timezone.now().isoformat(),
        "started_at": game.started_at.isoformat() if game.started_at else None,
        "active_at": game.active_at.isoformat() if game.active_at else None,
        "finished_at": game.finished_at.isoformat() if game.finished_at else None,
        "last_snapshot_released_at": game.last_snapshot_released_at.isoformat() if game.last_snapshot_released_at else None,
        "next_snapshot_at": next_release.isoformat() if next_release else None,
        "grace_period_seconds": game.grace_period_seconds,
        "snapshot_interval_seconds": game.snapshot_interval_seconds,
        "start_runner_count": game.start_runner_count,
        "players": [player_payload(p) for p in game.players.all()],
        "caught_players": [
            caught_payload(p)
            for p in game.players.filter(caught_at__isnull=False).order_by("-caught_at", "name")
        ],
        "current_player_id": current_player.id if current_player else None,
        "current_player_role": current_player.role if current_player else None,
        "is_host": bool(current_player and current_player.is_host),
    }
    if include_snapshots:
        payload["snapshots"] = [snapshot_payload(s) for s in latest_snapshots_for_game(game)]
    return payload
