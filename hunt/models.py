import random
import secrets
import string

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Game(models.Model):
    class Status(models.TextChoices):
        LOBBY = "lobby", "Lobby"
        GRACE = "grace_period", "Voorsprong"
        ACTIVE = "active", "Actief"
        FINISHED = "finished", "Afgelopen"

    code = models.CharField(max_length=6, unique=True, db_index=True)
    host_token = models.CharField(max_length=64, default=secrets.token_urlsafe, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LOBBY)
    start_runner_count = models.PositiveSmallIntegerField(default=1)
    grace_period_seconds = models.PositiveIntegerField(default=120)
    snapshot_interval_seconds = models.PositiveIntegerField(default=120)
    started_at = models.DateTimeField(null=True, blank=True)
    active_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_snapshot_released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code

    @classmethod
    def generate_code(cls):
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(alphabet, k=6))
            if not cls.objects.filter(code=code).exists():
                return code

    def clean(self):
        if self.start_runner_count not in (1, 2, 3):
            raise ValidationError("Het aantal start-runners moet 1, 2 of 3 zijn.")

    def update_status_from_time(self, save=True):
        if self.status == self.Status.GRACE and self.active_at and timezone.now() >= self.active_at:
            self.status = self.Status.ACTIVE
            if save:
                self.save(update_fields=["status"])

    def start(self):
        if self.status == self.Status.FINISHED:
            raise ValidationError("Een afgelopen spel kan niet opnieuw starten.")
        if self.status != self.Status.LOBBY:
            raise ValidationError("Dit spel is al gestart.")
        players = list(self.players.all())
        if len(players) < 2:
            raise ValidationError("Je hebt minimaal 2 spelers nodig.")

        chosen = [p for p in players if p.is_start_runner]
        if len(chosen) == 0:
            chosen = random.sample(players, min(self.start_runner_count, len(players)))
        if not 1 <= len(chosen) <= 3:
            raise ValidationError("Kies 1 tot 3 start-runners.")

        now = timezone.now()
        with transaction.atomic():
            self.started_at = now
            self.active_at = now + timezone.timedelta(seconds=self.grace_period_seconds)
            self.status = self.Status.GRACE
            self.last_snapshot_released_at = None
            self.save()
            Player.objects.filter(game=self).update(role=Player.Role.FUGITIVE, caught_at=None)
            Player.objects.filter(id__in=[p.id for p in chosen]).update(role=Player.Role.HUNTER)

    def return_to_lobby(self):
        if self.status == self.Status.LOBBY:
            return
        with transaction.atomic():
            LocationPing.objects.filter(game=self).delete()
            ReleasedLocationSnapshot.objects.filter(game=self).delete()
            Player.objects.filter(game=self).update(role=Player.Role.FUGITIVE, caught_at=None)
            self.status = self.Status.LOBBY
            self.started_at = None
            self.active_at = None
            self.finished_at = None
            self.last_snapshot_released_at = None
            self.save(
                update_fields=[
                    "status",
                    "started_at",
                    "active_at",
                    "finished_at",
                    "last_snapshot_released_at",
                ]
            )

    def release_snapshot_if_due(self):
        self.update_status_from_time()
        if self.status != self.Status.ACTIVE:
            return False
        now = timezone.now()
        if self.last_snapshot_released_at:
            due_at = self.last_snapshot_released_at + timezone.timedelta(seconds=self.snapshot_interval_seconds)
            if now < due_at:
                return False

        created = False
        with transaction.atomic():
            for player in self.players.filter(role=Player.Role.FUGITIVE):
                ping = player.location_pings.order_by("-created_at").first()
                if not ping:
                    continue
                ReleasedLocationSnapshot.objects.create(
                    game=self,
                    player=player,
                    latitude=ping.latitude,
                    longitude=ping.longitude,
                    accuracy=ping.accuracy,
                    pinged_at=ping.created_at,
                    released_at=now,
                )
                created = True
            self.last_snapshot_released_at = now
            self.save(update_fields=["last_snapshot_released_at", "status"])
        return created

    def finish_if_no_fugitives(self):
        if self.status in (self.Status.GRACE, self.Status.ACTIVE) and not self.players.filter(role=Player.Role.FUGITIVE).exists():
            self.status = self.Status.FINISHED
            self.finished_at = timezone.now()
            self.save(update_fields=["status", "finished_at"])
            return True
        return False


class Player(models.Model):
    class Role(models.TextChoices):
        HUNTER = "hunter", "Runner"
        FUGITIVE = "fugitive", "Vluchter"

    game = models.ForeignKey(Game, related_name="players", on_delete=models.CASCADE)
    access_token = models.CharField(max_length=64, default=secrets.token_urlsafe, unique=True)
    name = models.CharField(max_length=80)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FUGITIVE)
    is_host = models.BooleanField(default=False)
    is_start_runner = models.BooleanField(default=False)
    caught_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["joined_at", "id"]

    def __str__(self):
        return f"{self.name} ({self.game.code})"

    @property
    def role_label(self):
        return "runner" if self.role == self.Role.HUNTER else "vluchter"

    def mark_caught(self):
        if self.role != self.Role.FUGITIVE:
            raise ValidationError("Alleen vluchters kunnen aangeven dat ze gepakt zijn.")
        self.role = self.Role.HUNTER
        self.caught_at = timezone.now()
        self.save(update_fields=["role", "caught_at"])
        self.game.finish_if_no_fugitives()


class LocationPing(models.Model):
    game = models.ForeignKey(Game, related_name="location_pings", on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name="location_pings", on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReleasedLocationSnapshot(models.Model):
    game = models.ForeignKey(Game, related_name="released_snapshots", on_delete=models.CASCADE)
    player = models.ForeignKey(Player, related_name="released_snapshots", on_delete=models.CASCADE)
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy = models.FloatField(null=True, blank=True)
    pinged_at = models.DateTimeField()
    released_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-released_at", "player__name"]
