# SPEC.md

## 1. TECHNOLOGY STACK

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Language | Python | 3.12 (`python:3.12-slim`) | Only the standard library is used at runtime |
| Runtime deps | *None* | — | Explicit requirement: "Solo librería estándar (datetime, decimal), sin servidor ni interfaz" |
| Standard modules used | `datetime` (`date`, `timedelta`), `decimal` (`Decimal`, `ROUND_HALF_UP`), `typing` (`Literal`) | Python 3.12 stdlib | `datetime.datetime` is imported only to be **rejected** by the type guard |
| Test framework | `pytest` | `8.3.3` (pinned in `requirements-dev.txt`) | Dev-only dependency; tests are written by the Developer |
| Packaging style | Plain source directory `src/` imported as a namespace package | — | No `setup.py`/`pyproject.toml` packaging is required by the request |
| Containerization | Docker + Docker Compose | Docker Engine ≥ 24, Compose v2 | Library container runs the pytest suite and exits |
| Frontend | *None* | — | Explicitly excluded ("sin servidor ni interfaz") |
| Database | *None* | — | Explicitly excluded |

**Hard constraint:** no third-party runtime dependency may be added. `import` statements in `src/booking.py` are limited to `datetime`, `decimal`, `typing`.

---

## 2. DATA CONTRACTS

There is no database and no persistence. The contracts below are the module-level constants, type aliases and callable signatures that `src/booking.py` MUST expose verbatim.

### 2.1 Module constants and type aliases (`src/booking.py`)

```python
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

RoomType = Literal["single", "double", "suite"]

MONEY_QUANTUM: Decimal = Decimal("0.01")
MAX_NIGHTS: int = 30
WEEKEND_SURCHARGE: Decimal = Decimal("0.25")
TOURIST_TAX_PER_GUEST_PER_NIGHT: Decimal = Decimal("2.50")
LONG_STAY_NIGHTS: int = 7
LONG_STAY_DISCOUNT: Decimal = Decimal("0.10")

BASE_RATES: dict[RoomType, Decimal] = {
    "single": Decimal("50.00"),
    "double": Decimal("80.00"),
    "suite": Decimal("150.00"),
}

ROOM_CAPACITY: dict[RoomType, int] = {
    "single": 1,
    "double": 2,
    "suite": 4,
}

WEEKEND_WEEKDAYS: frozenset[int] = frozenset({4, 5})  # Friday=4, Saturday=5 (date.weekday())

__all__ = [
    "RoomType",
    "MONEY_QUANTUM",
    "MAX_NIGHTS",
    "WEEKEND_SURCHARGE",
    "TOURIST_TAX_PER_GUEST_PER_NIGHT",
    "LONG_STAY_NIGHTS",
    "LONG_STAY_DISCOUNT",
    "BASE_RATES",
    "ROOM_CAPACITY",
    "WEEKEND_WEEKDAYS",
    "nights",
    "nightly_rate",
    "stay_total",
]
```

### 2.2 Callable contracts

```python
def nights(check_in: date, check_out: date) -> int: ...

def nightly_rate(day: date, room: RoomType) -> Decimal: ...

def stay_total(check_in: date, check_out: date, room: RoomType, guests: int) -> Decimal: ...
```

| Function | Argument | Accepted type | Rejected with |
|---|---|---|---|
| `nights` | `check_in` | `datetime.date`, **not** `datetime.datetime` | `TypeError` |
| `nights` | `check_out` | `datetime.date`, **not** `datetime.datetime` | `TypeError` |
| `nightly_rate` | `day` | `datetime.date`, **not** `datetime.datetime` | `TypeError` |
| `nightly_rate` | `room` | one of `"single"`, `"double"`, `"suite"` | `ValueError` for anything else (including non-`str`) |
| `stay_total` | `check_in`, `check_out` | same as `nights` | `TypeError` / `ValueError` propagated from `nights()` |
| `stay_total` | `room` | one of `"single"`, `"double"`, `"suite"` | `ValueError` |
| `stay_total` | `guests` | `int`, **not** `bool` | `TypeError` when not `int` or when `bool`; `ValueError` when out of range |

### 2.3 Return-value contract

| Function | Return type | Rounding | Guarantee |
|---|---|---|---|
| `nights` | `int` | n/a | `1 <= result <= 30` |
| `nightly_rate` | `Decimal` | `quantize(MONEY_QUANTUM, ROUND_HALF_UP)` | Always 2 decimal places, exponent `-2` |
| `stay_total` | `Decimal` | `quantize(MONEY_QUANTUM, ROUND_HALF_UP)` | Always 2 decimal places, exponent `-2` |

`float` MUST NEVER be used in any calculation. All money values are constructed from string literals (`Decimal("50.00")`) to avoid binary floating-point artefacts.

### 2.4 Error contract (exact messages)

Private helper `_require_date(value, name)`:

```python
def _require_date(value: object, name: str) -> None:
    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise TypeError(f"{name} must be a datetime.date, got {type(value).__name__}")
```

| Condition | Exception | Message |
|---|---|---|
| `check_in` is `str`/`datetime.datetime`/`None`/… | `TypeError` | `"check_in must be a datetime.date, got str"` (type name interpolated) |
| `check_out` is `str`/`datetime.datetime`/… | `TypeError` | `"check_out must be a datetime.date, got datetime"` |
| `check_out <= check_in` | `ValueError` | `f"check_out ({check_out.isoformat()}) must be after check_in ({check_in.isoformat()})"` |
| `(check_out - check_in).days > 30` | `ValueError` | `f"stay cannot exceed {MAX_NIGHTS} nights, got {(check_out - check_in).days}"` |
| `room` not in `BASE_RATES` | `ValueError` | `f"unknown room type: {room!r}"` |
| `guests` is `bool` or not `int` | `TypeError` | `f"guests must be an int, got {type(guests).__name__}"` |
| `guests < 1` or `guests > ROOM_CAPACITY[room]` | `ValueError` | `f"guests must be between 1 and {ROOM_CAPACITY[room]} for room {room!r}, got {guests}"` |

**Validation order (deterministic, mandatory):**
1. `nights()` — date types (`TypeError`), then ordering (`ValueError`), then max-30 (`ValueError`).
2. `room` membership in `BASE_RATES` (`ValueError`).
3. `guests` type, including `bool` rejection (`TypeError`).
4. `guests` range against `ROOM_CAPACITY[room]` (`ValueError`).

Note the `bool` guard: `isinstance(True, int)` is `True` in Python, so the type guard MUST be written as `if isinstance(guests, bool) or not isinstance(guests, int): raise TypeError(...)`.

### 2.5 Calculation semantics (normative pseudocode)

```python
def nights(check_in, check_out):
    _require_date(check_in, "check_in")
    _require_date(check_out, "check_out")
    if check_out <= check_in:
        raise ValueError(...)
    delta = (check_out - check_in).days
    if delta > MAX_NIGHTS:
        raise ValueError(...)
    return delta


def nightly_rate(day, room):
    _require_date(day, "day")
    if room not in BASE_RATES:
        raise ValueError(f"unknown room type: {room!r}")
    rate = BASE_RATES[room]
    if day.weekday() in WEEKEND_WEEKDAYS:          # Friday or Saturday
        rate = rate * (Decimal("1") + WEEKEND_SURCHARGE)
    return rate.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def stay_total(check_in, check_out, room, guests):
    n = nights(check_in, check_out)                # step 1
    if room not in BASE_RATES:                     # step 2
        raise ValueError(f"unknown room type: {room!r}")
    if isinstance(guests, bool) or not isinstance(guests, int):   # step 3
        raise TypeError(f"guests must be an int, got {type(guests).__name__}")
    capacity = ROOM_CAPACITY[room]                 # step 4
    if guests < 1 or guests > capacity:
        raise ValueError(...)

    room_subtotal = Decimal("0.00")
    day = check_in
    for _ in range(n):
        room_subtotal += nightly_rate(day, room)
        day += timedelta(days=1)

    if n >= LONG_STAY_NIGHTS:
        discount = (room_subtotal * LONG_STAY_DISCOUNT).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
        room_subtotal = room_subtotal - discount

    tourist_tax = TOURIST_TAX_PER_GUEST_PER_NIGHT * guests * n
    total = room_subtotal + tourist_tax
    return total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
```

Nights iterated are `check_in`, `check_in + 1 day`, …, `check_out - 1 day` (the night that *starts* on `check_out` is **not** billed).

### 2.6 Reference rate table (used by tests)

| Room | Weekday (Mon–Thu, Sun) | Weekend (Fri, Sat) |
|---|---|---|
| `single` | `50.00` | `62.50` |
| `double` | `80.00` | `100.00` |
| `suite` | `150.00` | `187.50` |

`2026-01-01` is a **Thursday**, therefore `2026-01-02` is a **Friday** and `2026-01-05` is a **Monday**.

---

## 3. API ENDPOINTS

**None.** The request explicitly states: *"Solo librería estándar (datetime, decimal), sin servidor ni interfaz."* No HTTP server, no FastAPI, no Flask, no CLI entry point, no `if __name__ == "__main__"` block, no webhook, no observability endpoint.

The complete public surface of the library is its three Python callables, specified here as the authoritative "API" the consumer (hotel revenue team's Python scripts) imports:

| Callable | Signature | Returns | Raises |
|---|---|---|---|
| `nights` | `nights(check_in: date, check_out: date) -> int` | `int` in `[1, 30]` | `TypeError`, `ValueError` |
| `nightly_rate` | `nightly_rate(day: date, room: RoomType) -> Decimal` | `Decimal` with 2 dp | `TypeError`, `ValueError` |
| `stay_total` | `stay_total(check_in: date, check_out: date, room: RoomType, guests: int) -> Decimal` | `Decimal` with 2 dp | `TypeError`, `ValueError` |

Consumption example (must work verbatim against the delivered library):

```python
from datetime import date
from decimal import Decimal
from src.booking import stay_total

total = stay_total(date(2026, 1, 2), date(2026, 1, 4), "double", 2)
assert total == Decimal("210.00")
```

---

## 4. FILE STRUCTURE

```
hotel-stay-cost/
├── src/
│   └── booking.py            # The only production module: constants, type guards, nights(), nightly_rate(), stay_total()
├── tests/
│   └── test_booking.py       # pytest suite: example, weekend surcharge, 7-night discount, limits, validations
├── Dockerfile                # python:3.12-slim image; installs pytest and runs the test suite as CMD
├── docker-compose.yml        # Single service `booking-lib` that builds and runs the test suite
├── requirements-dev.txt      # pinned dev dependency: pytest==8.3.3 (no runtime dependencies)
├── pytest.ini                # pytest config: `pythonpath = .`, `testpaths = tests`
├── .env.example              # Documents that the library reads no environment variables (comments only)
├── .dockerignore             # Excludes .git, __pycache__, .pytest_cache, *.pyc from the build context
├── .gitignore                # Excludes __pycache__/, *.pyc, .pytest_cache/, .venv/, .env
└── README.md                 # Brief: purpose, install, usage example, business rules, how to run tests
```

### 4.1 PORT TABLE

| Service | Listening Port | Path |
|---|---|---|
| *(none)* | — | `src/booking.py` |

There are **no backend services and no exposed ports**. This is a pure library with no network listener; the Docker image runs `python -m pytest` and exits with the pytest exit code. Therefore:
- The `Dockerfile` contains **no `EXPOSE` instruction**.
- `docker-compose.yml` contains **no `ports:` mapping**.
- No host port in the 21000–65000 range is consumed.

### 4.2 SHARED MODULES

| Shared path | Imported by services |
|---|---|
| *(none)* | — |

`src/booking.py` is a single self-contained module with no cross-service imports. The `Dockerfile` copies `src/` and `tests/` into the image so the test suite can import `src.booking`.

### 4.3 Per-file responsibilities

| File | Must contain |
|---|---|
| `src/booking.py` | Module docstring; imports limited to `datetime`, `decimal`, `typing`; all constants from §2.1; `_require_date`; `_require_known_room`; `nights`; `nightly_rate`; `stay_total`; `__all__` |
| `tests/test_booking.py` | Imports `from decimal import Decimal`, `from datetime import date, datetime`, `import pytest`, `from src.booking import nights, nightly_rate, stay_total, BASE_RATES, ROOM_CAPACITY, MAX_NIGHTS`; test functions listed in §10 |
| `Dockerfile` | `FROM python:3.12-slim`; `WORKDIR /app`; copy and install `requirements-dev.txt`; copy `pytest.ini`, `src/`, `tests/`, `README.md`; `CMD ["python", "-m", "pytest", "-v"]` |
| `docker-compose.yml` | `services.booking-lib` with `build: {context: ., dockerfile: Dockerfile}` and `command: ["python", "-m", "pytest", "-v"]` |
| `README.md` | Purpose, install (`pip install -r requirements-dev.txt`), usage snippet, business-rule table (base rates, weekend surcharge, tourist tax, 7-night discount, capacity), test command (`python -m pytest -v`), note that only the standard library is required at runtime |

---

## 5. ENVIRONMENT VARIABLES

**The library reads no environment variables.** There is no configuration surface: rates, capacities, surcharges and thresholds are module constants (see §2.1). No API keys, no service URLs, no feature flags, no database URLs.

| Name | Type | Description | Example value |
|---|---|---|---|
| *(none)* | — | The library does not call `os.environ`, `os.getenv`, or any config loader | — |

`.env.example` exists only to make the absence explicit and to keep the repository template consistent:

```dotenv
# The hotel stay cost library reads NO environment variables.
# All rates, capacities and thresholds are module constants in src/booking.py.
#
# Optional, developer-only overrides understood by tooling (not by the library):
# PYTHONPATH=.
```

No environment variable influences behaviour; setting any of the above does not change the results of `nights`, `nightly_rate` or `stay_total`.

---

## 6. IMPORT CONTRACTS

### 6.1 From `src/booking.py` (public, stable)

```python
from src.booking import nights
from src.booking import nightly_rate
from src.booking import stay_total
from src.booking import RoomType
from src.booking import MONEY_QUANTUM
from src.booking import MAX_NIGHTS
from src.booking import WEEKEND_SURCHARGE
from src.booking import TOURIST_TAX_PER_GUEST_PER_NIGHT
from src.booking import LONG_STAY_NIGHTS
from src.booking import LONG_STAY_DISCOUNT
from src.booking import BASE_RATES
from src.booking import ROOM_CAPACITY
from src.booking import WEEKEND_WEEKDAYS
```

Combined, canonical test-file import line:

```python
from src.booking import (
    BASE_RATES,
    LONG_STAY_DISCOUNT,
    LONG_STAY_NIGHTS,
    MAX_NIGHTS,
    ROOM_CAPACITY,
    TOURIST_TAX_PER_GUEST_PER_NIGHT,
    WEEKEND_SURCHARGE,
    nights,
    nightly_rate,
    stay_total,
)
```

### 6.2 Third-party / standard imports permitted in `src/booking.py`

```python
from datetime import date, timedelta
import datetime                      # only for datetime.datetime rejection
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
```

No other imports are permitted in `src/booking.py`. `pytest` MUST NOT be imported there.

### 6.3 Private helpers (internal only, not exported in `__all__`)

```python
def _require_date(value: object, name: str) -> None: ...
def _require_known_room(room: object) -> None: ...
```

Tests MAY reference them but are not required to.

### 6.4 `pytest.ini` guarantees

```ini
[pytest]
pythonpath = .
testpaths = tests
```

`pythonpath = .` makes `from src.booking import ...` resolvable from the repository root and from inside the container (`WORKDIR /app`), without `setup.py`, `pyproject.toml`, or `conftest.py` sys.path hacking.

---

## 7. FRONTEND STATE & COMPONENT CONTRACTS

**Not applicable.** The request states the library has "sin servidor ni interfaz" and is used *"únicamente el equipo de revenue del hotel, como dependencia en sus scripts Python"*. There is:
- no React/Vue/Angular/Svelte application,
- no hooks, composables, services or stores,
- no components, props or design tokens.

Section 9 (DESIGN TOKENS) is intentionally omitted for the same reason: no UI/UX Design Implementation Contract exists for this project.

---

## 8. FILE EXTENSION CONVENTION

- **Project language:** Python only (no JavaScript, no TypeScript).
- **All source files use the `.py` extension.** There are no `.js`, `.jsx`, `.ts`, `.tsx`, `.vue` or `.svelte` files anywhere in the repository.
- **Production entry point:** `src/booking.py` — imported as `from src.booking import nights, nightly_rate, stay_total`.
- **Test entry point:** `tests/test_booking.py` — executed via `python -m pytest -v` (or `docker compose up --build`).
- There is **no `index.html`**, no bundler, no `package.json`.
- `src/` is a namespace package (no `__init__.py` file); import resolution is guaranteed by `pytest.ini`'s `pythonpath = .` and by `WORKDIR /app` in the container.

---

## 10. FUNCTIONAL REQUIREMENTS COVERAGE

| # | Requirement (verbatim traceability) | Implementation | Files |
|---|---|---|---|
| R1 | `nights(check_in, check_out) -> int`: nights between both `datetime.date` values | `return (check_out - check_in).days` after validation | `src/booking.py` (`nights`) |
| R2 | `check_out` must be after `check_in`, otherwise `ValueError` | `if check_out <= check_in: raise ValueError(...)` — equality is also rejected (zero-night stay invalid) | `src/booking.py` (`nights`) |
| R3 | Maximum stay is 30 nights, otherwise `ValueError` | `if (check_out - check_in).days > MAX_NIGHTS: raise ValueError(...)`; exactly 30 is allowed, 31 raises | `src/booking.py` (`nights`, `MAX_NIGHTS`) |
| R4 | If either argument is not a `date`, raise `TypeError` | `_require_date` uses `not isinstance(value, datetime.date)` | `src/booking.py` (`_require_date`) |
| R5 | If either argument is a `datetime` (i.e. `datetime.datetime`), raise `TypeError` | `_require_date` checks `isinstance(value, datetime.datetime)` **first**, because `datetime` subclasses `date` | `src/booking.py` (`_require_date`) |
| R6 | `nightly_rate(day, room) -> Decimal` with base rates single 50.00, double 80.00, suite 150.00 | `BASE_RATES` dict of `Decimal` string literals; lookup by `room` | `src/booking.py` (`BASE_RATES`, `nightly_rate`) |
| R7 | Friday and Saturday nights carry a 25% surcharge | `if day.weekday() in WEEKEND_WEEKDAYS: rate *= Decimal("1") + WEEKEND_SURCHARGE`, with `WEEKEND_WEEKDAYS = frozenset({4, 5})` | `src/booking.py` (`WEEKEND_WEEKDAYS`, `WEEKEND_SURCHARGE`, `nightly_rate`) |
| R8 | Round to 2 decimals using `ROUND_HALF_UP` | `.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)` on every money return value | `src/booking.py` (`MONEY_QUANTUM`, `nightly_rate`, `stay_total`) |
| R9 | Unknown room raises `ValueError` | `if room not in BASE_RATES: raise ValueError(f"unknown room type: {room!r}")`; also applied in `stay_total` | `src/booking.py` (`nightly_rate`, `stay_total`) |
| R10 | `stay_total` sums `nightly_rate` for each night from `check_in` up to the day before `check_out` | `for _ in range(n): room_subtotal += nightly_rate(day, room); day += timedelta(days=1)` | `src/booking.py` (`stay_total`) |
| R11 | Tourist tax of 2.50 per guest per night | `TOURIST_TAX_PER_GUEST_PER_NIGHT * guests * n` added after the room discount is applied | `src/booking.py` (`TOURIST_TAX_PER_GUEST_PER_NIGHT`, `stay_total`) |
| R12 | Stays of 7 nights or more: 10% discount applied **only** to the room subtotal, never to the tax | `if n >= LONG_STAY_NIGHTS: room_subtotal -= (room_subtotal * LONG_STAY_DISCOUNT).quantize(...)`; the tax is added **after** the discount line | `src/booking.py` (`LONG_STAY_NIGHTS`, `LONG_STAY_DISCOUNT`, `stay_total`) |
| R13 | Final total rounded to 2 decimals `ROUND_HALF_UP` | `return total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)` | `src/booking.py` (`stay_total`) |
| R14 | `guests` must be `int`; `bool` must raise `TypeError` | `if isinstance(guests, bool) or not isinstance(guests, int): raise TypeError(...)` | `src/booking.py` (`stay_total`) |
| R15 | `guests` must be between 1 and the room capacity (single 1, double 2, suite 4), otherwise `ValueError` | `if guests < 1 or guests > ROOM_CAPACITY[room]: raise ValueError(...)` | `src/booking.py` (`ROOM_CAPACITY`, `stay_total`) |
| R16 | Worked example: 2026-01-02 → 2026-01-04, `"double"`, 2 guests = `210.00` | Fri 100.00 + Sat 100.00 = 200.00 room subtotal; no discount (< 7 nights); tax 2.50 × 2 × 2 = 10.00; total 210.00 | `src/booking.py`, `tests/test_booking.py::test_reference_example` |
| R17a | Test: reference example | `assert stay_total(date(2026,1,2), date(2026,1,4), "double", 2) == Decimal("210.00")` | `tests/test_booking.py::test_reference_example` |
| R17b | Test: weekend surcharge | Asserts `nightly_rate` for Fri/Sat equals base × 1.25 (`62.50`/`100.00`/`187.50`) and that Mon/Tue/Wed/Thu/Sun equal base | `tests/test_booking.py::test_weekend_surcharge` |
| R17c | Test: 7-night discount | `stay_total(date(2026,1,5), date(2026,1,12), "double", 2) == Decimal("575.00")` (subtotal 600.00 − 60.00 + tax 35.00). A 6-night control case (`2026-01-05`→`2026-01-11`, `"double"`, 2) asserts `550.00` with **no** discount | `tests/test_booking.py::test_long_stay_discount`, `test_no_discount_under_seven_nights` |
| R17d | Test: discount applies only to the room subtotal, not the tax | Asserts the tax component equals `2.50 * guests * nights` unchanged in a ≥7-night stay, and that the discount equals exactly 10% of the undiscounted room subtotal | `tests/test_booking.py::test_discount_excludes_tourist_tax` |
| R17e | Test: limits (30-night max) | `nights(date(2026,1,5), date(2026,2,4)) == 30` (accepted); `nights(date(2026,1,5), date(2026,2,5))` raises `ValueError` | `tests/test_booking.py::test_max_stay_limit` |
| R17f | Test: validations (types, unknown room, guest bounds) | `pytest.raises(TypeError)` for `datetime(2026,1,2)` and for a `str`; `pytest.raises(ValueError)` for `check_out == check_in` and `check_out < check_in`; `pytest.raises(ValueError)` for `"penthouse"`; `pytest.raises(TypeError)` for `guests=True` and `guests=2.0`; `pytest.raises(ValueError)` for `guests=0` and for `guests > ROOM_CAPACITY[room]`; asserts `("single", 1)`, `("double", 2)`, `("suite", 4)` are accepted | `tests/test_booking.py::test_nights_type_errors`, `test_nights_value_errors`, `test_unknown_room_raises`, `test_guests_validation` |
| R17g | Test: `nightly_rate` rounding contract | Asserts every returned rate has exponent `Decimal("-2")` (`rate.as_tuple().exponent == -2`) | `tests/test_booking.py::test_rates_have_two_decimals` |
| R18 | Brief README | Purpose, install, usage example, business rules table, test command, stdlib-only note | `README.md` |
| R19 | Standard library only (`datetime`, `decimal`), no third-party runtime deps | Imports restricted as in §6.2; `requirements-dev.txt` pins only `pytest==8.3.3` for testing | `src/booking.py`, `requirements-dev.txt` |
| R20 | No server, no interface, no CLI | No `main`/`__main__` block, no HTTP framework, no argparse; `Dockerfile` has no `EXPOSE` | `src/booking.py`, `Dockerfile` |
| R21 | Consumed as a dependency by the hotel revenue team's Python scripts | Public API importable as `from src.booking import nights, nightly_rate, stay_total`; stable `__all__`; README documents the import path and the `Decimal` return type | `src/booking.py`, `README.md` |
| R22 | Containerization requirement for the deliverable | `Dockerfile` (`python:3.12-slim`, installs dev requirements, copies `src/`+`tests/`+`pytest.ini`, `CMD ["python","-m","pytest","-v"]`) and `docker-compose.yml` service `booking-lib` that builds and runs the suite | `Dockerfile`, `docker-compose.yml`, `.dockerignore` |
| R23 | Tests authored by the Developer only (no QA, no DevSec team) | Test suite lives in `tests/test_booking.py` and is written as part of the Developer deliverable; no separate QA/Security artifacts exist in the tree | `tests/test_booking.py` |

### 10.1 Mandatory test assertions (exact expected values)

| Case | Call | Expected |
|---|---|---|
| Reference example | `stay_total(date(2026,1,2), date(2026,1,4), "double", 2)` | `Decimal("210.00")` |
| Friday single rate | `nightly_rate(date(2026,1,2), "single")` | `Decimal("62.50")` |
| Saturday suite rate | `nightly_rate(date(2026,1,3), "suite")` | `Decimal("187.50")` |
| Sunday double rate | `nightly_rate(date(2026,1,4), "double")` | `Decimal("80.00")` |
| Monday single rate | `nightly_rate(date(2026,1,5), "single")` | `Decimal("50.00")` |
| 7-night double, 2 guests | `stay_total(date(2026,1,5), date(2026,1,12), "double", 2)` | `Decimal("575.00")` |
| 6-night double, 2 guests (no discount) | `stay_total(date(2026,1,5), date(2026,1,11), "double", 2)` | `Decimal("550.00")` |
| 7-night single, 1 guest | `stay_total(date(2026,1,5), date(2026,1,12), "single", 1)` | `Decimal("355.00")` |
| Nights count | `nights(date(2026,1,2), date(2026,1,4))` | `2` |
| Max stay accepted | `nights(date(2026,1,5), date(2026,2,4))` | `30` |

### 10.2 Explicit non-goals (must NOT be generated)

- No REST/GraphQL/RPC API, no FastAPI/Flask, no `uvicorn`, no port binding.
- No database, ORM, migration, cache, queue or background worker.
- No frontend, HTML templates, CSS, or design tokens.
- No logging framework, metrics endpoint, tracing, or dashboards.
- No mocks, stubs, or placeholder implementations anywhere in `src/booking.py`.
- No CLI script, `argparse`, or `__main__` guard.
- No third-party runtime dependency of any kind.