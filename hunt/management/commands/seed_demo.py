from django.core.management.base import BaseCommand

from hunt.models import Game, Player


class Command(BaseCommand):
    help = "Maak een demo-game met vier spelers."

    def handle(self, *args, **options):
        game = Game.objects.create(code=Game.generate_code(), grace_period_seconds=30, snapshot_interval_seconds=30)
        names = ["Host", "Sam", "Noor", "Bo"]
        for index, name in enumerate(names):
            Player.objects.create(game=game, name=name, is_host=index == 0)
        self.stdout.write(self.style.SUCCESS(f"Demo-game gemaakt met code {game.code}"))
