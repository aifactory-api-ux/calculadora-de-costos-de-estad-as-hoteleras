"""Suite de pruebas de la librería de cálculo de estadías hoteleras.

Cubre el contrato público de :mod:`src.booking`: ejemplo de referencia,
recargo de fin de semana, descuento por estancia larga, exclusividad del
descuento respecto de la tasa turística, límites de estadía y validaciones
de tipos y valores.

Los importes se comparan siempre contra :class:`decimal.Decimal` para no
introducir artefactos de punto flotante en las aserciones.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

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


def test_reference_example():
    """Ejemplo de referencia: dos noches de fin de semana en habitación doble."""
    total = stay_total(date(2026, 1, 2), date(2026, 1, 4), "double", 2)

    assert nights(date(2026, 1, 2), date(2026, 1, 4)) == 2
    assert nightly_rate(date(2026, 1, 2), "double") == Decimal("100.00")
    assert nightly_rate(date(2026, 1, 3), "double") == Decimal("100.00")
    assert total == Decimal("210.00")


def test_weekend_surcharge():
    """Viernes y sábado llevan recargo; el resto de días mantiene la tarifa base."""
    viernes = date(2026, 1, 2)
    sabado = date(2026, 1, 3)
    domingo = date(2026, 1, 4)
    lunes = date(2026, 1, 5)

    assert nightly_rate(viernes, "single") == Decimal("62.50")
    assert nightly_rate(viernes, "double") == Decimal("100.00")
    assert nightly_rate(viernes, "suite") == Decimal("187.50")
    assert nightly_rate(sabado, "single") == Decimal("62.50")
    assert nightly_rate(sabado, "double") == Decimal("100.00")
    assert nightly_rate(sabado, "suite") == Decimal("187.50")

    assert nightly_rate(domingo, "single") == Decimal("50.00")
    assert nightly_rate(domingo, "double") == Decimal("80.00")
    assert nightly_rate(domingo, "suite") == Decimal("150.00")
    assert nightly_rate(lunes, "single") == Decimal("50.00")
    assert nightly_rate(lunes, "double") == Decimal("80.00")
    assert nightly_rate(lunes, "suite") == Decimal("150.00")

    # El recargo equivale a aplicar un 25 % sobre la tarifa base.
    recargo = Decimal("1") + WEEKEND_SURCHARGE
    for room, base in BASE_RATES.items():
        assert nightly_rate(viernes, room) == (base * recargo).quantize(Decimal("0.01"))
        assert nightly_rate(sabado, room) == (base * recargo).quantize(Decimal("0.01"))


def test_long_stay_discount():
    """Las estancias de 7 noches o más reciben el 10 % de descuento."""
    assert LONG_STAY_NIGHTS == 7

    assert stay_total(date(2026, 1, 5), date(2026, 1, 12), "double", 2) == Decimal(
        "575.00"
    )
    assert stay_total(date(2026, 1, 5), date(2026, 1, 12), "single", 1) == Decimal(
        "355.00"
    )


def test_no_discount_under_seven_nights():
    """Con 6 noches no se aplica descuento alguno."""
    assert stay_total(date(2026, 1, 5), date(2026, 1, 11), "double", 2) == Decimal(
        "550.00"
    )


def test_discount_excludes_tourist_tax():
    """El descuento se aplica solo al subtotal de habitación, nunca a la tasa."""
    check_in = date(2026, 1, 5)
    check_out = date(2026, 1, 12)
    room = "double"
    guests = 2
    total_nights = nights(check_in, check_out)

    subtotal = Decimal("0.00")
    for offset in range(total_nights):
        subtotal += nightly_rate(check_in + timedelta(days=offset), room)

    tax = TOURIST_TAX_PER_GUEST_PER_NIGHT * guests * total_nights
    room_after_discount = subtotal * (Decimal("1") - LONG_STAY_DISCOUNT)
    total = stay_total(check_in, check_out, room, guests)

    # La tasa turística se cobra íntegra y el descuento es el 10 % del subtotal.
    assert tax == Decimal("35.00")
    assert room_after_discount == Decimal("540.0000")
    assert total - room_after_discount == tax
    assert total == room_after_discount + tax


def test_max_stay_limit():
    """La estadía máxima es de 30 noches."""
    assert nights(date(2026, 1, 5), date(2026, 2, 4)) == MAX_NIGHTS
    assert MAX_NIGHTS == 30

    with pytest.raises(ValueError, match="cannot exceed 30 nights"):
        nights(date(2026, 1, 5), date(2026, 2, 5))


def test_nights_count():
    """La cantidad de noches es la diferencia entre ambas fechas."""
    assert nights(date(2026, 1, 2), date(2026, 1, 4)) == 2
    assert nights(date(2026, 1, 5), date(2026, 1, 6)) == 1


def test_nights_type_errors():
    """Las fechas deben ser datetime.date y nunca datetime.datetime."""
    with pytest.raises(TypeError):
        nights(datetime(2026, 1, 2), date(2026, 1, 4))
    with pytest.raises(TypeError):
        nights(date(2026, 1, 2), datetime(2026, 1, 4))
    with pytest.raises(TypeError):
        nights("2026-01-02", date(2026, 1, 4))
    with pytest.raises(TypeError):
        nights(None, date(2026, 1, 4))


def test_nights_value_errors():
    """El egreso debe ser posterior al ingreso."""
    with pytest.raises(ValueError):
        nights(date(2026, 1, 2), date(2026, 1, 2))
    with pytest.raises(ValueError):
        nights(date(2026, 1, 4), date(2026, 1, 2))


def test_unknown_room_raises():
    """Un tipo de habitación desconocido se rechaza con ValueError."""
    with pytest.raises(ValueError, match="unknown room type"):
        nightly_rate(date(2026, 1, 2), "penthouse")
    with pytest.raises(ValueError, match="unknown room type"):
        stay_total(date(2026, 1, 2), date(2026, 1, 4), "penthouse", 2)


def test_guests_validation():
    """Los huéspedes deben ser un int dentro de la capacidad de la habitación."""
    check_in = date(2026, 1, 5)
    check_out = date(2026, 1, 6)

    with pytest.raises(TypeError):
        stay_total(check_in, check_out, "double", True)
    with pytest.raises(TypeError):
        stay_total(check_in, check_out, "double", 2.0)

    with pytest.raises(ValueError):
        stay_total(check_in, check_out, "single", 0)
    with pytest.raises(ValueError):
        stay_total(check_in, check_out, "single", ROOM_CAPACITY["single"] + 1)
    with pytest.raises(ValueError):
        stay_total(check_in, check_out, "double", ROOM_CAPACITY["double"] + 1)
    with pytest.raises(ValueError):
        stay_total(check_in, check_out, "suite", ROOM_CAPACITY["suite"] + 1)

    for room, guests in (("single", 1), ("double", 2), ("suite", 4)):
        assert ROOM_CAPACITY[room] == guests
        total = stay_total(check_in, check_out, room, guests)
        assert isinstance(total, Decimal)


def test_rates_have_two_decimals():
    """Toda tarifa y todo total se devuelven con exactamente dos decimales."""
    inicio = date(2026, 1, 5)

    for offset in range(7):
        day = inicio + timedelta(days=offset)
        for room in BASE_RATES:
            rate = nightly_rate(day, room)
            assert rate.as_tuple().exponent == -2
            assert isinstance(rate, Decimal)

    for room in BASE_RATES:
        total = stay_total(inicio, inicio + timedelta(days=3), room, 1)
        assert total.as_tuple().exponent == -2
        assert isinstance(total, Decimal)
