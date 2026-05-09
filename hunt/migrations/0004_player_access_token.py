import secrets

from django.db import migrations, models


def fill_access_tokens(apps, schema_editor):
    Player = apps.get_model("hunt", "Player")
    for player in Player.objects.all():
        player.access_token = secrets.token_urlsafe(32)
        player.save(update_fields=["access_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("hunt", "0003_game_host_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="access_token",
            field=models.CharField(default=secrets.token_urlsafe, max_length=64),
        ),
        migrations.RunPython(fill_access_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="player",
            name="access_token",
            field=models.CharField(default=secrets.token_urlsafe, max_length=64, unique=True),
        ),
    ]
