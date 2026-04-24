"""FnO-compatible unit conversion UDFs for morph-kgc.

These functions are registered by morph-kgc via the ``udfs=`` INI option.
Each ``@udf`` decorator maps an FnO function IRI to a Python implementation.
The YARRRML compiler references these IRIs in ``function:`` blocks; morph-kgc
resolves them to these implementations at materialize time.
"""

try:
    from morph_kgc.udfs import udf  # pyright: ignore[reportMissingImports]
except ImportError:
    # Allow import without morph-kgc installed (for testing, linting, etc.)
    def udf(**kwargs):  # type: ignore[misc]
        """No-op decorator stub when morph-kgc is not available."""

        def decorator(fn):  # type: ignore[misc]
            return fn

        return decorator


_RFNS = "https://rosetta.interop/functions#"
_GREL_VALUE = "http://users.ugent.be/~bjdmeest/function/grel.ttl#valueParameter"


@udf(fun_id=f"{_RFNS}meterToFoot", value=_GREL_VALUE)
def meter_to_foot(value: str) -> float:
    """Convert meters to feet."""
    return float(value) * 3.28084


@udf(fun_id=f"{_RFNS}footToMeter", value=_GREL_VALUE)
def foot_to_meter(value: str) -> float:
    """Convert feet to meters."""
    return float(value) * 0.3048


@udf(fun_id=f"{_RFNS}kilogramToPound", value=_GREL_VALUE)
def kilogram_to_pound(value: str) -> float:
    """Convert kilograms to pounds."""
    return float(value) * 2.20462


@udf(fun_id=f"{_RFNS}poundToKg", value=_GREL_VALUE)
def pound_to_kg(value: str) -> float:
    """Convert pounds to kilograms."""
    return float(value) / 2.20462


@udf(fun_id=f"{_RFNS}celsiusToFahrenheit", value=_GREL_VALUE)
def celsius_to_fahrenheit(value: str) -> float:
    """Convert Celsius to Fahrenheit."""
    return float(value) * 1.8 + 32.0


@udf(fun_id=f"{_RFNS}kelvinToCelsius", value=_GREL_VALUE)
def kelvin_to_celsius(value: str) -> float:
    """Convert Kelvin to Celsius."""
    return float(value) - 273.15
