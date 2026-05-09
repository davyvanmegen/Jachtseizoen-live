from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("hunt", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="last_seen",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
