from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from urllib.parse import parse_qs

from .models import Game, Player
from .services import game_payload


class GameConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.code = self.scope["url_route"]["kwargs"]["code"]
        self.group_name = f"game_{self.code}"
        game_exists = await database_sync_to_async(Game.objects.filter(code=self.code).exists)()
        if not game_exists:
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(await self.get_payload())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json(await self.get_payload())

    async def game_update(self, event):
        await self.send_json(await self.get_payload())

    @database_sync_to_async
    def get_current_player(self):
        game = Game.objects.get(code=self.code)
        token_player = self.get_token_player(game)
        if token_player:
            return token_player
        player_id = self.scope["session"].get(f"game_{game.id}_player_id")
        if not player_id:
            return None
        return Player.objects.filter(game=game, id=player_id).first()

    @database_sync_to_async
    def get_payload(self):
        game = Game.objects.prefetch_related("players").get(code=self.code)
        player = self.get_token_player(game)
        if not player:
            player_id = self.scope["session"].get(f"game_{game.id}_player_id")
            player = Player.objects.filter(game=game, id=player_id).first() if player_id else None
        include = bool(player and player.role == Player.Role.HUNTER)
        return game_payload(game, player, include_snapshots=include)

    def get_token_player(self, game):
        raw_query = self.scope.get("query_string", b"").decode("utf-8")
        query = parse_qs(raw_query)
        player_id = (query.get("player_id") or [None])[0]
        token = (query.get("token") or [None])[0]
        if not player_id or not token:
            return None
        return Player.objects.filter(game=game, id=player_id, access_token=token).first()
