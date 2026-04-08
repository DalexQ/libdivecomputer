"""
Modelos de datos para representar la información de buceo extraída.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GasMix:
    """Mezcla de gases utilizada durante el buceo."""
    index: int = 0
    helium: float = 0.0    # Porcentaje
    oxygen: float = 21.0   # Porcentaje
    nitrogen: float = 79.0 # Porcentaje
    usage: str = "none"     # none, oxygen, diluent, sidemount

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "helium_pct": round(self.helium, 1),
            "oxygen_pct": round(self.oxygen, 1),
            "nitrogen_pct": round(self.nitrogen, 1),
            "usage": self.usage,
        }


@dataclass
class Tank:
    """Datos del tanque de buceo."""
    gasmix_index: int = 0
    type: str = "none"            # none, metric, imperial
    volume_liters: float = 0.0
    workpressure_bar: float = 0.0
    beginpressure_bar: float = 0.0
    endpressure_bar: float = 0.0
    usage: str = "none"

    def to_dict(self) -> dict:
        return {
            "gasmix_index": self.gasmix_index,
            "type": self.type,
            "volume_liters": round(self.volume_liters, 1),
            "workpressure_bar": round(self.workpressure_bar, 2),
            "beginpressure_bar": round(self.beginpressure_bar, 2),
            "endpressure_bar": round(self.endpressure_bar, 2),
            "usage": self.usage,
        }


@dataclass
class DiveSample:
    """Una muestra de datos durante el buceo (tomada en un instante de tiempo)."""
    time_seconds: float = 0.0
    depth_meters: float = 0.0
    temperature_celsius: Optional[float] = None
    pressure_bar: Optional[float] = None
    pressure_tank: Optional[int] = None
    heartbeat: Optional[int] = None
    bearing: Optional[int] = None
    setpoint: Optional[float] = None
    ppo2: Optional[float] = None
    cns: Optional[float] = None
    deco_type: Optional[str] = None
    deco_time: Optional[int] = None
    deco_depth: Optional[float] = None
    gasmix_index: Optional[int] = None
    events: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "time_seconds": round(self.time_seconds, 3),
            "depth_meters": round(self.depth_meters, 2),
        }
        if self.temperature_celsius is not None:
            d["temperature_celsius"] = round(self.temperature_celsius, 2)
        if self.pressure_bar is not None:
            d["pressure_bar"] = round(self.pressure_bar, 2)
            d["pressure_tank"] = self.pressure_tank
        if self.heartbeat is not None:
            d["heartbeat"] = self.heartbeat
        if self.bearing is not None:
            d["bearing"] = self.bearing
        if self.setpoint is not None:
            d["setpoint"] = round(self.setpoint, 2)
        if self.ppo2 is not None:
            d["ppo2"] = round(self.ppo2, 2)
        if self.cns is not None:
            d["cns"] = round(self.cns, 1)
        if self.deco_type is not None:
            d["deco_type"] = self.deco_type
            d["deco_time"] = self.deco_time
            d["deco_depth"] = round(self.deco_depth, 2) if self.deco_depth else None
        if self.gasmix_index is not None:
            d["gasmix_index"] = self.gasmix_index
        if self.events:
            d["events"] = self.events
        return d

    def to_csv_row(self) -> dict:
        """Devuelve un diccionario plano para CSV."""
        return {
            "time_seconds": round(self.time_seconds, 3),
            "depth_meters": round(self.depth_meters, 2),
            "temperature_celsius": round(self.temperature_celsius, 2) if self.temperature_celsius is not None else "",
            "pressure_bar": round(self.pressure_bar, 2) if self.pressure_bar is not None else "",
            "heartbeat": self.heartbeat if self.heartbeat is not None else "",
            "ppo2": round(self.ppo2, 2) if self.ppo2 is not None else "",
            "cns": round(self.cns, 1) if self.cns is not None else "",
        }


@dataclass
class DecoModel:
    """Modelo de descompresión utilizado."""
    type: str = "none"  # none, buhlmann, vpm, rgbm, dciem
    conservatism: int = 0
    gf_low: int = 0
    gf_high: int = 0

    def to_dict(self) -> dict:
        d = {"type": self.type, "conservatism": self.conservatism}
        if self.type == "buhlmann" and (self.gf_low or self.gf_high):
            d["gf_low"] = self.gf_low
            d["gf_high"] = self.gf_high
        return d


@dataclass
class Location:
    """Ubicación GPS del buceo."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0

    def to_dict(self) -> dict:
        return {
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "altitude": round(self.altitude, 2),
        }


@dataclass
class DiveData:
    """Datos completos de un buceo individual."""
    number: int = 0
    source_file: str = ""

    # Fecha y hora
    datetime_str: str = ""
    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    minute: int = 0
    second: int = 0
    timezone_offset: Optional[int] = None  # seconds

    # Campos principales
    divetime_seconds: int = 0
    maxdepth_meters: float = 0.0
    avgdepth_meters: float = 0.0

    # Temperaturas (Celsius)
    temperature_surface: Optional[float] = None
    temperature_minimum: Optional[float] = None
    temperature_maximum: Optional[float] = None

    # Modo de buceo
    divemode: str = "oc"  # freedive, gauge, oc, ccr, scr

    # Modelo de descompresión
    decomodel: Optional[DecoModel] = None

    # Salinidad
    salinity_type: Optional[str] = None  # fresh, salt
    salinity_density: Optional[float] = None

    # Presión atmosférica
    atmospheric_bar: Optional[float] = None

    # Ubicación
    location: Optional[Location] = None

    # Mezclas de gases
    gasmixes: list = field(default_factory=list)

    # Tanques
    tanks: list = field(default_factory=list)

    # Muestras de datos
    samples: list = field(default_factory=list)

    # Fingerprint
    fingerprint: str = ""

    # Raw data size
    data_size: int = 0

    def format_datetime(self) -> str:
        """Formatea la fecha y hora del buceo."""
        if self.datetime_str:
            return self.datetime_str
        dt = f"{self.year:04d}-{self.month:02d}-{self.day:02d} {self.hour:02d}:{self.minute:02d}:{self.second:02d}"
        if self.timezone_offset is not None:
            sign = "+" if self.timezone_offset >= 0 else "-"
            tz_abs = abs(self.timezone_offset)
            dt += f" {sign}{tz_abs // 3600:02d}:{(tz_abs % 3600) // 60:02d}"
        return dt

    def format_divetime(self) -> str:
        """Formatea el tiempo de buceo como MM:SS."""
        return f"{self.divetime_seconds // 60:02d}:{self.divetime_seconds % 60:02d}"

    def to_dict(self) -> dict:
        """Convierte a diccionario para serialización."""
        d = {
            "number": self.number,
            "source_file": self.source_file,
            "datetime": self.format_datetime(),
            "divetime_seconds": self.divetime_seconds,
            "divetime_formatted": self.format_divetime(),
            "maxdepth_meters": round(self.maxdepth_meters, 2),
            "avgdepth_meters": round(self.avgdepth_meters, 2),
            "divemode": self.divemode,
        }

        if self.temperature_surface is not None:
            d["temperature_surface_celsius"] = round(self.temperature_surface, 1)
        if self.temperature_minimum is not None:
            d["temperature_minimum_celsius"] = round(self.temperature_minimum, 1)
        if self.temperature_maximum is not None:
            d["temperature_maximum_celsius"] = round(self.temperature_maximum, 1)

        if self.decomodel:
            d["decomodel"] = self.decomodel.to_dict()

        if self.salinity_type:
            d["salinity"] = {"type": self.salinity_type}
            if self.salinity_density:
                d["salinity"]["density"] = round(self.salinity_density, 1)

        if self.atmospheric_bar is not None:
            d["atmospheric_bar"] = round(self.atmospheric_bar, 5)

        if self.location:
            d["location"] = self.location.to_dict()

        if self.gasmixes:
            d["gasmixes"] = [gm.to_dict() for gm in self.gasmixes]

        if self.tanks:
            d["tanks"] = [t.to_dict() for t in self.tanks]

        if self.fingerprint:
            d["fingerprint"] = self.fingerprint

        d["data_size_bytes"] = self.data_size
        d["sample_count"] = len(self.samples)
        d["samples"] = [s.to_dict() for s in self.samples]

        return d

    def to_summary_csv_row(self) -> dict:
        """Devuelve un diccionario plano para el resumen CSV."""
        return {
            "dive_number": self.number,
            "source_file": self.source_file,
            "datetime": self.format_datetime(),
            "divetime_minutes": round(self.divetime_seconds / 60.0, 1),
            "maxdepth_meters": round(self.maxdepth_meters, 2),
            "avgdepth_meters": round(self.avgdepth_meters, 2),
            "temp_surface_c": round(self.temperature_surface, 1) if self.temperature_surface is not None else "",
            "temp_min_c": round(self.temperature_minimum, 1) if self.temperature_minimum is not None else "",
            "temp_max_c": round(self.temperature_maximum, 1) if self.temperature_maximum is not None else "",
            "divemode": self.divemode,
            "gasmix_count": len(self.gasmixes),
            "sample_count": len(self.samples),
            "data_size_bytes": self.data_size,
            "fingerprint": self.fingerprint,
        }
