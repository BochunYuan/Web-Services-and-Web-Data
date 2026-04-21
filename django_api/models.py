from django.db import models
from django.utils import timezone


class User(models.Model):
    username = models.CharField(max_length=50, unique=True, db_index=True)
    email = models.EmailField(max_length=100, unique=True, db_index=True)
    hashed_password = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.username

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False


class Driver(models.Model):
    driver_ref = models.CharField(max_length=50, unique=True, db_index=True)
    driver_number = models.IntegerField(null=True, blank=True)
    code = models.CharField(max_length=3, null=True, blank=True)
    forename = models.CharField(max_length=50)
    surname = models.CharField(max_length=50, db_index=True)
    dob = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    url = models.URLField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "drivers"
        ordering = ["surname"]

    def __str__(self) -> str:
        return f"{self.forename} {self.surname}"


class Team(models.Model):
    constructor_ref = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    nationality = models.CharField(max_length=50, null=True, blank=True)
    url = models.URLField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "teams"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Circuit(models.Model):
    circuit_ref = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    alt = models.FloatField(null=True, blank=True)
    url = models.URLField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "circuits"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Race(models.Model):
    year = models.IntegerField(db_index=True)
    round = models.IntegerField()
    name = models.CharField(max_length=100)
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    url = models.URLField(max_length=255, null=True, blank=True)
    circuit = models.ForeignKey(
        Circuit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="races",
        db_column="circuit_id",
    )

    class Meta:
        db_table = "races"
        ordering = ["-year", "round"]
        constraints = [
            models.UniqueConstraint(fields=["year", "round"], name="uq_races_year_round"),
        ]

    def __str__(self) -> str:
        return f"{self.year} R{self.round} {self.name}"


class Result(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="results", db_column="race_id")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="results", db_column="driver_id")
    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="results",
        db_column="constructor_id",
    )
    grid = models.IntegerField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    position_text = models.CharField(max_length=5, null=True, blank=True)
    position_order = models.IntegerField(null=True, blank=True)
    points = models.FloatField(default=0.0)
    laps = models.IntegerField(null=True, blank=True)
    time_text = models.CharField(max_length=20, null=True, blank=True)
    milliseconds = models.IntegerField(null=True, blank=True)
    fastest_lap = models.IntegerField(null=True, blank=True)
    fastest_lap_time = models.CharField(max_length=20, null=True, blank=True)
    fastest_lap_speed = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    class Meta:
        db_table = "results"
        ordering = ["race_id", "position_order"]
        indexes = [
            models.Index(fields=["race"]),
            models.Index(fields=["driver"]),
            models.Index(fields=["team"]),
        ]

    def __str__(self) -> str:
        return f"Result race={self.race_id} driver={self.driver_id} pos={self.position}"
