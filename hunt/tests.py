import json

from asgiref.sync import async_to_sync
from django.test import Client, TestCase
from django.urls import reverse

from .consumers import GameConsumer
from .models import Game, LocationPing, Player, ReleasedLocationSnapshot
from .services import game_payload, latest_snapshots_for_game


class GameFlowTests(TestCase):
    def test_create_game(self):
        response = self.client.post(reverse("home"), {"action": "create", "create-name": "Davy"})
        self.assertEqual(response.status_code, 302)
        game = Game.objects.get()
        self.assertEqual(game.players.count(), 1)
        self.assertTrue(game.players.get().is_host)

    def test_join_game(self):
        game = Game.objects.create(code="ABC123")
        response = self.client.post(reverse("home"), {"action": "join", "join-name": "Sam", "join-code": "abc123"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Player.objects.filter(game=game, name="Sam").exists())

    def test_player_token_keeps_host_tab_separate_from_join_tab(self):
        create_response = self.client.post(reverse("home"), {"action": "create", "create-name": "Host"})
        self.assertEqual(create_response.status_code, 302)
        game = Game.objects.get()
        host = game.players.get(is_host=True)

        join_response = self.client.post(
            reverse("home"),
            {"action": "join", "join-name": "Extra", "join-code": game.code},
        )

        self.assertEqual(join_response.status_code, 302)
        self.assertEqual(Player.objects.filter(game=game).count(), 2)
        response = self.client.get(
            reverse("state", args=[game.code]),
            {"player_id": host.id, "token": host.access_token},
        )
        self.assertTrue(response.json()["is_host"])
        self.assertEqual(response.json()["current_player_id"], host.id)

    def test_host_starts_game(self):
        game = Game.objects.create(code="ABC123", start_runner_count=1)
        host = Player.objects.create(game=game, name="Host", is_host=True, is_start_runner=True)
        Player.objects.create(game=game, name="Noor")
        session = self.client.session
        session[f"game_{game.id}_player_id"] = host.id
        session.save()
        response = self.client.post(reverse("start_game", args=[game.code]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        host.refresh_from_db()
        self.assertEqual(game.status, Game.Status.GRACE)
        self.assertEqual(host.role, Player.Role.HUNTER)

    def test_start_game_returns_json_error_with_too_few_players(self):
        game = Game.objects.create(code="ABC123", start_runner_count=1)
        host = Player.objects.create(game=game, name="Host", is_host=True, is_start_runner=True)
        session = self.client.session
        session[f"game_{game.id}_player_id"] = host.id
        session.save()
        response = self.client.post(
            reverse("start_game", args=[game.code]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("minimaal 2 spelers", response.json()["error"])

    def test_non_host_settings_post_returns_json_403(self):
        game = Game.objects.create(code="ABC123")
        Player.objects.create(game=game, name="Host", is_host=True)
        player = Player.objects.create(game=game, name="Noor")
        session = self.client.session
        session[f"game_{game.id}_player_id"] = player.id
        session.save()

        response = self.client.post(
            reverse("update_settings", args=[game.code]),
            {
                "start_runner_count": 1,
                "grace_period_seconds": 120,
                "snapshot_interval_seconds": 120,
                "start_runner_ids": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("Alleen de host", response.json()["error"])

    def test_host_can_choose_manual_start_runner(self):
        game = Game.objects.create(code="ABC123", start_runner_count=1)
        host = Player.objects.create(game=game, name="Host", is_host=True)
        chosen = Player.objects.create(game=game, name="Sam")
        fugitive = Player.objects.create(game=game, name="Noor")
        session = self.client.session
        session[f"game_{game.id}_player_id"] = host.id
        session.save()

        response = self.client.post(
            reverse("update_settings", args=[game.code]),
            {
                "start_runner_count": 1,
                "grace_period_seconds": 120,
                "snapshot_interval_seconds": 120,
                "start_runner_ids": str(chosen.id),
            },
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("start_game", args=[game.code]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        chosen.refresh_from_db()
        fugitive.refresh_from_db()
        self.assertEqual(chosen.role, Player.Role.HUNTER)
        self.assertEqual(fugitive.role, Player.Role.FUGITIVE)

    def test_player_becomes_runner_after_caught(self):
        game = Game.objects.create(code="ABC123", status=Game.Status.ACTIVE)
        player = Player.objects.create(game=game, name="Noor", role=Player.Role.FUGITIVE)
        Player.objects.create(game=game, name="Runner", role=Player.Role.HUNTER)
        session = self.client.session
        session[f"game_{game.id}_player_id"] = player.id
        session.save()
        response = self.client.post(reverse("mark_caught", args=[game.code]))
        self.assertEqual(response.status_code, 200)
        player.refresh_from_db()
        self.assertEqual(player.role, Player.Role.HUNTER)
        self.assertIsNotNone(player.caught_at)
        payload = game_payload(game, player)
        self.assertEqual(payload["caught_players"][0]["name"], "Noor")

    def test_game_finishes_when_all_fugitives_are_caught(self):
        game = Game.objects.create(code="ABC123", status=Game.Status.ACTIVE)
        player = Player.objects.create(game=game, name="Laatste", role=Player.Role.FUGITIVE)
        Player.objects.create(game=game, name="Runner", role=Player.Role.HUNTER)
        session = self.client.session
        session[f"game_{game.id}_player_id"] = player.id
        session.save()
        response = self.client.post(reverse("mark_caught", args=[game.code]))
        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.status, Game.Status.FINISHED)

    def test_host_can_stop_game_back_to_lobby(self):
        game = Game.objects.create(code="ABC123", status=Game.Status.ACTIVE)
        host = Player.objects.create(game=game, name="Host", is_host=True, role=Player.Role.HUNTER)
        fugitive = Player.objects.create(game=game, name="Noor", role=Player.Role.FUGITIVE)
        ping = LocationPing.objects.create(game=game, player=fugitive, latitude=52.0, longitude=5.0)
        ReleasedLocationSnapshot.objects.create(
            game=game,
            player=fugitive,
            latitude=ping.latitude,
            longitude=ping.longitude,
            pinged_at=ping.created_at,
        )
        session = self.client.session
        session[f"game_{game.id}_player_id"] = host.id
        session.save()

        response = self.client.post(reverse("stop_game", args=[game.code]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        host.refresh_from_db()
        self.assertEqual(game.status, Game.Status.LOBBY)
        self.assertEqual(host.role, Player.Role.FUGITIVE)
        self.assertEqual(LocationPing.objects.filter(game=game).count(), 0)
        self.assertEqual(ReleasedLocationSnapshot.objects.filter(game=game).count(), 0)

    def test_latest_snapshots_include_all_uncaught_fugitives(self):
        game = Game.objects.create(code="ABC123", status=Game.Status.ACTIVE)
        first = Player.objects.create(game=game, name="Noor", role=Player.Role.FUGITIVE)
        second = Player.objects.create(game=game, name="Sam", role=Player.Role.FUGITIVE)
        caught = Player.objects.create(game=game, name="Bo", role=Player.Role.HUNTER)
        for player in (first, second, caught):
            ping = LocationPing.objects.create(game=game, player=player, latitude=52.0, longitude=5.0)
            ReleasedLocationSnapshot.objects.create(
                game=game,
                player=player,
                latitude=ping.latitude,
                longitude=ping.longitude,
                pinged_at=ping.created_at,
            )

        player_ids = {snapshot.player_id for snapshot in latest_snapshots_for_game(game)}

        self.assertEqual(player_ids, {first.id, second.id})

    def test_player_can_send_location_ping(self):
        game = Game.objects.create(code="ABC123", status=Game.Status.ACTIVE)
        player = Player.objects.create(game=game, name="Noor", role=Player.Role.FUGITIVE)
        session = self.client.session
        session[f"game_{game.id}_player_id"] = player.id
        session.save()

        response = self.client.post(
            reverse("location_ping", args=[game.code]),
            data=json.dumps({"latitude": 52.1, "longitude": 5.1, "accuracy": 12}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(LocationPing.objects.filter(game=game, player=player).count(), 1)

    def test_game_page_sets_csrf_cookie_for_location_fetches(self):
        game = Game.objects.create(code="ABC123", status=Game.Status.ACTIVE)
        player = Player.objects.create(game=game, name="Noor", role=Player.Role.FUGITIVE)
        session = self.client.session
        session[f"game_{game.id}_player_id"] = player.id
        session.save()

        response = self.client.get(reverse("game", args=[game.code]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    def test_consumer_payload_is_personalized_for_host(self):
        game = Game.objects.create(code="ABC123")
        host = Player.objects.create(game=game, name="Host", is_host=True)
        consumer = GameConsumer()
        consumer.code = game.code
        consumer.scope = {
            "session": {},
            "query_string": f"player_id={host.id}&token={host.access_token}".encode("utf-8"),
        }

        payload = async_to_sync(consumer.get_payload)()

        self.assertTrue(payload["is_host"])
        self.assertEqual(payload["current_player_id"], host.id)
