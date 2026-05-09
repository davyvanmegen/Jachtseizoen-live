from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Game",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(db_index=True, max_length=6, unique=True)),
                ("status", models.CharField(choices=[("lobby", "Lobby"), ("grace_period", "Voorsprong"), ("active", "Actief"), ("finished", "Afgelopen")], default="lobby", max_length=20)),
                ("start_runner_count", models.PositiveSmallIntegerField(default=1)),
                ("grace_period_seconds", models.PositiveIntegerField(default=120)),
                ("snapshot_interval_seconds", models.PositiveIntegerField(default=120)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("active_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_snapshot_released_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Player",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("role", models.CharField(choices=[("hunter", "Runner"), ("fugitive", "Vluchter")], default="fugitive", max_length=20)),
                ("is_host", models.BooleanField(default=False)),
                ("is_start_runner", models.BooleanField(default=False)),
                ("caught_at", models.DateTimeField(blank=True, null=True)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("game", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="players", to="hunt.game")),
            ],
            options={"ordering": ["joined_at", "id"]},
        ),
        migrations.CreateModel(
            name="LocationPing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("accuracy", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("game", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="location_pings", to="hunt.game")),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="location_pings", to="hunt.player")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ReleasedLocationSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("accuracy", models.FloatField(blank=True, null=True)),
                ("pinged_at", models.DateTimeField()),
                ("released_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("game", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="released_snapshots", to="hunt.game")),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="released_snapshots", to="hunt.player")),
            ],
            options={"ordering": ["-released_at", "player__name"]},
        ),
    ]
