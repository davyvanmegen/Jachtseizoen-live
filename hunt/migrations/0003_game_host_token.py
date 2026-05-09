import secrets

from django.db import migrations, models


def fill_host_tokens(apps, schema_editor):
    Game = apps.get_model("hunt", "Game")
    for game in Game.objects.all():
        game.host_token = secrets.token_urlsafe(32)
        game.save(update_fields=["host_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("hunt", "0002_player_last_seen"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="host_token",
            field=models.CharField(default=secrets.token_urlsafe, max_length=64),
        ),
        migrations.RunPython(fill_host_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="game",
            name="host_token",
            field=models.CharField(default=secrets.token_urlsafe, max_length=64, unique=True),
        ),
    ]
