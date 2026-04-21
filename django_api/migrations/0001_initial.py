from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Circuit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("circuit_ref", models.CharField(db_index=True, max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("location", models.CharField(blank=True, max_length=100, null=True)),
                ("country", models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ("lat", models.FloatField(blank=True, null=True)),
                ("lng", models.FloatField(blank=True, null=True)),
                ("alt", models.FloatField(blank=True, null=True)),
                ("url", models.URLField(blank=True, max_length=255, null=True)),
            ],
            options={"db_table": "circuits", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Driver",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("driver_ref", models.CharField(db_index=True, max_length=50, unique=True)),
                ("driver_number", models.IntegerField(blank=True, null=True)),
                ("code", models.CharField(blank=True, max_length=3, null=True)),
                ("forename", models.CharField(max_length=50)),
                ("surname", models.CharField(db_index=True, max_length=50)),
                ("dob", models.DateField(blank=True, null=True)),
                ("nationality", models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ("url", models.URLField(blank=True, max_length=255, null=True)),
            ],
            options={"db_table": "drivers", "ordering": ["surname"]},
        ),
        migrations.CreateModel(
            name="Team",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("constructor_ref", models.CharField(db_index=True, max_length=50, unique=True)),
                ("name", models.CharField(db_index=True, max_length=100)),
                ("nationality", models.CharField(blank=True, max_length=50, null=True)),
                ("url", models.URLField(blank=True, max_length=255, null=True)),
            ],
            options={"db_table": "teams", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(db_index=True, max_length=50, unique=True)),
                ("email", models.EmailField(db_index=True, max_length=100, unique=True)),
                ("hashed_password", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"db_table": "users"},
        ),
        migrations.CreateModel(
            name="Race",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.IntegerField(db_index=True)),
                ("round", models.IntegerField()),
                ("name", models.CharField(max_length=100)),
                ("date", models.DateField(blank=True, null=True)),
                ("time", models.TimeField(blank=True, null=True)),
                ("url", models.URLField(blank=True, max_length=255, null=True)),
                (
                    "circuit",
                    models.ForeignKey(
                        blank=True,
                        db_column="circuit_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="races",
                        to="django_api.circuit",
                    ),
                ),
            ],
            options={"db_table": "races", "ordering": ["-year", "round"]},
        ),
        migrations.CreateModel(
            name="Result",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("grid", models.IntegerField(blank=True, null=True)),
                ("position", models.IntegerField(blank=True, null=True)),
                ("position_text", models.CharField(blank=True, max_length=5, null=True)),
                ("position_order", models.IntegerField(blank=True, null=True)),
                ("points", models.FloatField(default=0.0)),
                ("laps", models.IntegerField(blank=True, null=True)),
                ("time_text", models.CharField(blank=True, max_length=20, null=True)),
                ("milliseconds", models.IntegerField(blank=True, null=True)),
                ("fastest_lap", models.IntegerField(blank=True, null=True)),
                ("fastest_lap_time", models.CharField(blank=True, max_length=20, null=True)),
                ("fastest_lap_speed", models.FloatField(blank=True, null=True)),
                ("status", models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                (
                    "driver",
                    models.ForeignKey(
                        db_column="driver_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="django_api.driver",
                    ),
                ),
                (
                    "race",
                    models.ForeignKey(
                        db_column="race_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="django_api.race",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        blank=True,
                        db_column="constructor_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="results",
                        to="django_api.team",
                    ),
                ),
            ],
            options={"db_table": "results", "ordering": ["race_id", "position_order"]},
        ),
        migrations.AddConstraint(
            model_name="race",
            constraint=models.UniqueConstraint(fields=("year", "round"), name="uq_races_year_round"),
        ),
        migrations.AddIndex(model_name="result", index=models.Index(fields=["race"], name="results_race_id_idx")),
        migrations.AddIndex(model_name="result", index=models.Index(fields=["driver"], name="results_driver_id_idx")),
        migrations.AddIndex(model_name="result", index=models.Index(fields=["team"], name="results_team_id_idx")),
    ]

