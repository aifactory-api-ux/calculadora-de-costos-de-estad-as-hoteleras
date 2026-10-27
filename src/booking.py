"""Cálculo de costos de estadías hoteleras.

Librería de dominio, sin dependencias externas ni estado global, que expone
tres funciones públicas:

- :func:`nights`: cantidad de noches facturadas de una estadía.
- :func:`nightly_rate`: tarifa de la noche que comienza en una fecha dada.
- :func:`stay_total`: costo total de una estadía (habitación + tasa turística).

Todos los importes monetarios se expresan con :class:`decimal.Decimal` para
evitar los artefactos del punto flotante binario.
"""

import datetime
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
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

# Viernes=4 y sábado=5 según date.weekday().
WEEKEND_WEEKDAYS: frozenset[int] = frozenset({4, 5})

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


def _require_date(value: object, name: str) -> None:
    """Valida que un valor sea una fecha de calendario.

    Args:
        value: Valor a validar.
        name: Nombre del argumento, interpolado en el mensaje de error.

    Raises:
        TypeError: Si el valor no es una instancia de :class:`datetime.date`,
            o si es una instancia de :class:`datetime.datetime`.
    """
    # datetime.datetime hereda de datetime.date, por eso se rechaza primero.
    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise TypeError(f"{name} must be a datetime.date, got {type(value).__name__}")


def _require_known_room(room: object) -> None:
    """Valida que el tipo de habitación exista en la tabla de tarifas.

    Args:
        room: Tipo de habitación a validar.

    Raises:
        ValueError: Si el tipo de habitación no es ``"single"``, ``"double"``
            ni ``"suite"``.
    """
    if not isinstance(room, str) or room not in BASE_RATES:
        raise ValueError(f"unknown room type: {room!r}")


def nights(check_in: date, check_out: date) -> int:
    """Calcula la cantidad de noches de una estadía.

    Args:
        check_in: Fecha de ingreso.
        check_out: Fecha de egreso, posterior a ``check_in``.

    Returns:
        int: Número de noches facturadas, entre 1 y ``MAX_NIGHTS``.

    Raises:
        TypeError: Si alguna fecha no es un :class:`datetime.date` (tampoco se
            acepta una instancia de :class:`datetime.datetime`).
        ValueError: Si ``check_out`` no es posterior a ``check_in`` o si la
            estadía supera ``MAX_NIGHTS`` noches.
    """
    _require_date(check_in, "check_in")
    _require_date(check_out, "check_out")
    if check_out <= check_in:
        raise ValueError(
            f"check_out ({check_out.isoformat()}) must be after check_in "
            f"({check_in.isoformat()})"
        )
    total_nights = (check_out - check_in).days
    if total_nights > MAX_NIGHTS:
        raise ValueError(f"stay cannot exceed {MAX_NIGHTS} nights, got {total_nights}")
    return total_nights


def nightly_rate(day: date, room: RoomType) -> Decimal:
    """Calcula la tarifa de la noche que comienza en ``day``.

    Las noches de viernes y sábado llevan un recargo del 25 %.

    Args:
        day: Fecha en la que comienza la noche facturada.
        room: Tipo de habitación.

    Returns:
        Decimal: Tarifa con dos decimales, redondeada con ``ROUND_HALF_UP``.

    Raises:
        TypeError: Si ``day`` no es un :class:`datetime.date`.
        ValueError: Si el tipo de habitación es desconocido.
    """
    _require_date(day, "day")
    _require_known_room(room)
    rate = BASE_RATES[room]
    if day.weekday() in WEEKEND_WEEKDAYS:
        rate = rate * (Decimal("1") + WEEKEND_SURCHARGE)
    return rate.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def stay_total(
    check_in: date, check_out: date, room: RoomType, guests: int
) -> Decimal:
    """Calcula el costo total de una estadía.

    El total suma las tarifas de cada noche facturada (desde ``check_in``
    hasta el día previo a ``check_out``), el descuento por estancia larga
    aplicado únicamente al subtotal de habitación y la tasa turística por
    huésped y por noche.

    Args:
        check_in: Fecha de ingreso.
        check_out: Fecha de egreso, posterior a ``check_in``.
        room: Tipo de habitación.
        guests: Cantidad de huéspedes, entre 1 y la capacidad de la habitación.

    Returns:
        Decimal: Costo total con dos decimales, redondeado con ``ROUND_HALF_UP``.

    Raises:
        TypeError: Si alguna fecha no es un :class:`datetime.date` o si
            ``guests`` no es un ``int`` (un ``bool`` no se acepta).
        ValueError: Si la estadía es inválida, si el tipo de habitación es
            desconocido o si la cantidad de huéspedes excede la capacidad.
    """
    total_nights = nights(check_in, check_out)
    _require_known_room(room)
    if isinstance(guests, bool) or not isinstance(guests, int):
        raise TypeError(f"guests must be an int, got {type(guests).__name__}")
    capacity = ROOM_CAPACITY[room]
    if guests < 1 or guests > capacity:
        raise ValueError(
            f"guests must be between 1 and {capacity} for room {room!r}, got {guests}"
        )

    room_subtotal = Decimal("0.00")
    day = check_in
    for _ in range(total_nights):
        room_subtotal += nightly_rate(day, room)
        day += timedelta(days=1)

    if total_nights >= LONG_STAY_NIGHTS:
        discount = (room_subtotal * LONG_STAY_DISCOUNT).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
        room_subtotal -= discount

    tourist_tax = TOURIST_TAX_PER_GUEST_PER_NIGHT * guests * total_nights
    total = room_subtotal + tourist_tax
    return total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
