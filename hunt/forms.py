from django import forms

from .models import Game, Player


class CreateGameForm(forms.Form):
    name = forms.CharField(max_length=80, label="Je naam")


class JoinGameForm(forms.Form):
    name = forms.CharField(max_length=80, label="Je naam")
    code = forms.CharField(max_length=6, label="Gamecode")

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class HostSettingsForm(forms.ModelForm):
    start_runner_ids = forms.CharField(required=False)

    class Meta:
        model = Game
        fields = ["start_runner_count", "grace_period_seconds", "snapshot_interval_seconds"]

    def clean_start_runner_count(self):
        count = self.cleaned_data["start_runner_count"]
        if count not in (1, 2, 3):
            raise forms.ValidationError("Kies 1, 2 of 3 start-runners.")
        return count

    def clean_grace_period_seconds(self):
        value = self.cleaned_data["grace_period_seconds"]
        if value < 10:
            raise forms.ValidationError("Gebruik minstens 10 seconden voorsprong.")
        return value

    def clean_snapshot_interval_seconds(self):
        value = self.cleaned_data["snapshot_interval_seconds"]
        if value < 10:
            raise forms.ValidationError("Gebruik minstens 10 seconden interval.")
        return value

    def selected_players(self, game):
        raw = self.cleaned_data.get("start_runner_ids", "")
        ids = [int(v) for v in raw.split(",") if v.strip().isdigit()]
        qs = Player.objects.filter(game=game, id__in=ids)
        if qs.count() not in (0, 1, 2, 3):
            raise forms.ValidationError("Kies maximaal 3 start-runners.")
        return qs
