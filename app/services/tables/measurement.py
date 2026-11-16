"""表格数值证据共用的技术值和单位词法。"""

import re
from typing import Literal


MEASUREMENT_UNITS = frozenset({
    "ps", "ns", "µs", "μs", "us", "ms", "s", "Hz", "kHz", "MHz", "GHz", "THz",
    "pA", "nA", "µA", "μA", "uA", "mA", "A", "pV", "nV", "µV", "μV", "uV", "mV", "V", "kV",
    "Ω", "mΩ", "kΩ", "MΩ", "F", "pF", "nF", "µF", "uF", "H", "nH", "µH", "mH",
    "W", "mW", "µW", "kW", "VA", "kVA", "MVA", "var", "°C", "K", "dB", "dBm", "ppm", "%",
    "C", "pC", "nC", "µC", "mC", "J", "mJ", "S", "mS", "B", "bit", "bits", "bps", "kbps", "Mbps",
})
MAX_PARAMETER_VALUE_CHARS = 64
MAX_PARAMETER_UNIT_CHARS = 32
ValueColumnLabel = Literal["MIN", "TYP", "MAX", "LOW", "NOM", "HIGH", "最小", "典型", "最大"]
PARAMETER_VALUE = re.compile(
    r"(?:[<>]=?|[≤≥≈~])? *[+−±-]? *(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+−-]?[0-9]+)?"
)
_UNIT_SEPARATOR = re.compile(r"[/·⋅*]")


def is_measurement_unit(value: str) -> bool:
    return 0 < len(value) <= MAX_PARAMETER_UNIT_CHARS and all(
        item.strip().removeprefix("√") in MEASUREMENT_UNITS for item in _UNIT_SEPARATOR.split(value)
    )


def split_parameter_value(text: str) -> tuple[str, str | None] | None:
    """整个单元格须为单个数值，可带已知单位。"""
    if len(text) > MAX_PARAMETER_VALUE_CHARS + MAX_PARAMETER_UNIT_CHARS + 1:
        return None
    value_match = PARAMETER_VALUE.match(text)
    if value_match is None or value_match.end() > MAX_PARAMETER_VALUE_CHARS:
        return None
    unit = text[value_match.end():].strip()
    if unit and not is_measurement_unit(unit):
        return None
    return value_match.group(), unit or None
