# Calculadora de Costos de Estadías Hoteleras

Librería Python que calcula el costo de las estadías de un hotel: cantidad de
noches facturadas, tarifa de cada noche y total de la estadía (habitación más
tasa turística), aplicando las reglas comerciales del hotel.

- Sin servidor, sin interfaz, sin CLI y sin base de datos.
- En runtime usa **solo la biblioteca estándar** (`datetime`, `decimal`); no
  tiene dependencias de terceros.
- Todos los importes se devuelven como `decimal.Decimal` con exactamente dos
  decimales (redondeo `ROUND_HALF_UP`).

## Instalación

### Requisitos

| Camino de ejecución | Requisitos |
|---|---|
| Host (`./run.sh`, `python -m pytest`) | Python 3.12 y `pip` |
| Contenedor (`docker compose up --build --abort-on-container-exit`) | Docker Engine ≥ 24 con Compose v2 (`docker compose`) |

No hay otros prerrequisitos: la librería en runtime solo usa la biblioteca
estándar de Python 3.12.

Para trabajar con la librería y su suite de pruebas:

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt` solo instala `pytest` (dependencia de desarrollo). Para
consumir la librería desde los scripts del equipo de revenue no hace falta
instalar nada: alcanza con tener Python 3.12 y que la raíz del repositorio
esté en el `PYTHONPATH` (por ejemplo `PYTHONPATH=.`).

## Uso

```python
from datetime import date
from decimal import Decimal

from src.booking import nights, nightly_rate, stay_total

total = stay_total(date(2026, 1, 2), date(2026, 1, 4), "double", 2)

assert nights(date(2026, 1, 2), date(2026, 1, 4)) == 2
assert nightly_rate(date(2026, 1, 2), "double") == Decimal("100.00")
assert total == Decimal("210.00")
```

El ejemplo factura dos noches de fin de semana (viernes 2026-01-02 y sábado
2026-01-03) en habitación doble: `100.00 + 100.00` de habitación más la tasa
turística `2.50 × 2 huéspedes × 2 noches = 10.00`, es decir
`Decimal("210.00")`.

### API pública

| Función | Descripción | Tipo de retorno |
|---|---|---|
| `nights(check_in, check_out)` | Cantidad de noches facturadas de la estadía | `int` |
| `nightly_rate(day, room)` | Tarifa de la noche que comienza en `day` | `Decimal` |
| `stay_total(check_in, check_out, room, guests)` | Total de la estadía (habitación + tasa turística) | `Decimal` |

Los tipos de habitación aceptados son `"single"`, `"double"` y `"suite"`.

## Reglas de negocio

| Regla | Valor |
|---|---|
| Tarifa base `single` | `50.00` por noche |
| Tarifa base `double` | `80.00` por noche |
| Tarifa base `suite` | `150.00` por noche |
| Recargo de fin de semana | `25 %` en las noches de viernes y sábado (`62.50` / `100.00` / `187.50`) |
| Tasa turística | `2.50` por huésped por noche |
| Descuento por estancia larga | `10 %` desde las 7 noches, aplicado solo al subtotal de habitación (la tasa turística no se descuenta) |
| Capacidad por habitación | `single` 1, `double` 2, `suite` 4 huéspedes |
| Estadía máxima | 30 noches |

Las noches facturadas van desde `check_in` hasta el día previo a `check_out`:
la noche que comienza en `check_out` no se cobra. `check_out` debe ser
posterior a `check_in`.

### Validaciones

| Situación | Excepción |
|---|---|
| Fecha que no es `datetime.date` (también se rechaza `datetime.datetime`) | `TypeError` |
| `check_out` no posterior a `check_in` | `ValueError` |
| Estadía de más de 30 noches | `ValueError` |
| Habitación distinta de `single`, `double` o `suite` | `ValueError` |
| `guests` que no es `int` (un `bool` no se acepta) | `TypeError` |
| `guests` fuera del rango `1..capacidad` de la habitación | `ValueError` |

## Pruebas

En el host, con la raíz del repositorio como directorio de trabajo:

```bash
python -m pytest -v
```

Con Docker, mediante el servicio `booking-lib` de `docker-compose.yml`:

```bash
docker compose up --build --abort-on-container-exit
```

El contenedor ejecuta la misma suite y termina con el código de salida de
pytest. No publica puertos, porque la librería no expone ningún listener.

El script `run.sh` reúne ambos caminos y es el punto de arranque del proyecto:

```bash
./run.sh            # entorno virtual local (.venv) + suite de pruebas
./run.sh --docker   # construye la imagen y corre la suite en el contenedor
```

Como la librería no expone ningún proceso de larga duración, arrancar el
proyecto equivale a ejecutar su suite de pruebas.

## Estructura

```
src/booking.py         # módulo de dominio: constantes, validaciones y cálculos
tests/test_booking.py  # suite de pruebas
pytest.ini             # configuración de pytest (pythonpath = ., testpaths = tests)
requirements-dev.txt   # dependencia de desarrollo: pytest==8.3.3
Dockerfile             # imagen de verificación de la suite
docker-compose.yml     # orquestación local del servicio booking-lib
run.sh                 # script de arranque y verificación (host o contenedor)
```

## Notas

- No hay variables de entorno: tarifas, capacidades y umbrales son constantes
  de módulo en `src/booking.py` (ver `.env.example`).
- `src/` es un paquete de espacio de nombres (sin `__init__.py`), por eso el
  import es `from src.booking import nights, nightly_rate, stay_total` desde
  la raíz del repositorio.
