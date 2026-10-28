"""Deterministic identity data shared by the Postgres seed and the event generator.

The rows in `compose/init/postgres/03_seed.sql` and the users produced here must
agree: the lab joins login events to Postgres users in later modules. If you
change one side, change the other and re-run `make fixtures`.
"""

from __future__ import annotations

from dataclasses import dataclass

FIRST_NAMES = [
    "Avery", "Marta", "Noah", "Priya", "Lucas", "Sofia", "Kenji", "Amara",
    "Elena", "Omar", "Ingrid", "Mateo", "Zara", "Felix", "Nadia", "Hugo",
    "Leila", "Tomas", "Yuna", "Ravi",
]
LAST_NAMES = [
    "Chen", "Silva", "Kowalski", "Nair", "Fischer", "Rossi", "Tanaka",
    "Okafor", "Petrova", "Haddad", "Larsen", "Garcia", "Khan", "Weber",
    "Novak", "Moreau", "Ali", "Kovac", "Park", "Iyer",
]
COUNTRIES = [
    "United States", "United Kingdom", "Germany", "France", "Netherlands",
    "Spain", "Canada", "Australia", "Japan", "Brazil", "India", "South Africa",
]
CITIES = [
    "New York", "London", "Berlin", "Paris", "Amsterdam", "Madrid",
    "Toronto", "Sydney", "Tokyo", "Sao Paulo", "Bengaluru", "Cape Town",
]
LATITUDES = [
    40.7128, 51.5074, 52.5200, 48.8566, 52.3676, 40.4168,
    43.6532, -33.8688, 35.6762, -23.5505, 12.9716, -33.9249,
]
LONGITUDES = [
    -74.0060, -0.1278, 13.4050, 2.3522, 4.9041, -3.7038,
    -79.3832, 151.2093, 139.6503, -46.6333, 77.5946, 18.4241,
]
DEPARTMENTS = ["Engineering", "Security", "Finance", "Sales", "Support", "Legal", "People"]

USER_COUNT = 2000


@dataclass(frozen=True)
class User:
    index: int
    user_id: str
    email: str
    full_name: str
    role_id: int
    account_status: str
    department: str
    home_country: str
    home_city: str
    home_lat: float
    home_lon: float
    mfa_enabled: bool
    deleted: bool

    @property
    def active(self) -> bool:
        return self.account_status == "active" and not self.deleted


def user_for(index: int) -> User:
    """1-based index, matching the `generate_series(1, 2000)` seed."""
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    last = LAST_NAMES[(index * 7) % len(LAST_NAMES)]
    geo = index % len(COUNTRIES)
    status = "active"
    if index % 47 == 0 or index % 20 == 0:
        status = "disabled"
    elif index % 20 == 1:
        status = "locked"
    elif index % 20 == 2:
        status = "suspended"
    return User(
        index=index,
        user_id=f"00000000-0000-0000-0000-{index:012d}",
        email=f"{first.lower()}.{last.lower()}{index}@acme.example",
        full_name=f"{first} {last}",
        role_id=1 + (index % 5),
        account_status=status,
        department=DEPARTMENTS[index % len(DEPARTMENTS)],
        home_country=COUNTRIES[geo],
        home_city=CITIES[geo],
        home_lat=LATITUDES[geo],
        home_lon=LONGITUDES[geo],
        mfa_enabled=(index % 5) != 0,
        deleted=index % 47 == 0,
    )


USERS = tuple(user_for(i) for i in range(1, USER_COUNT + 1))
