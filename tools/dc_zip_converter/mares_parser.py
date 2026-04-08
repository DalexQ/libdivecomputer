"""
Parser especializado para Mares Puck 4 / Genius family.

Parsea la estructura especifica de los archivos ZIP exportados por el software
de Mares para computadoras tipo Genius: Puck4, Genius, Horizon, Quad2, etc.

Formato del ZIP:
  - device.info: texto con informacion del dispositivo
  - flash.bin: dump de memoria flash
  - logbook/header_XXXX.bin: cabecera de 200 bytes por buceo (formato Genius v1)
  - logbook/data_XXXX.bin: datos de muestras por buceo (records DSTR/DPRS/DEND)
"""

import os
import struct
import zipfile
from typing import List, Optional, Tuple

from .models import DiveData, DiveSample, GasMix, Tank, DecoModel
from .console import Console

# Record type markers (ASCII as 32-bit LE)
DSTR_TYPE = 0x44535452  # "DSTR" - Dive Start Record
TISS_TYPE = 0x54495353  # "TISS" - Tissue Record
DPRS_TYPE = 0x44505253  # "DPRS" - Depth/Pressure Sample Record
SDPT_TYPE = 0x53445054  # "SDPT" - SCR sample record
AIRS_TYPE = 0x41495253  # "AIRS" - Air Integration Record
DEND_TYPE = 0x44454E44  # "DEND" - Dive End Record

# Record sizes (including the 4-byte type marker and 4-byte end marker + 2-byte CRC)
DSTR_SIZE = 58
TISS_SIZE = 138
DPRS_SIZE = 34
SDPT_SIZE = 78
DEND_SIZE = 162
AIRS_SIZE = 16

# Dive modes (Genius family)
GENIUS_AIR = 0
GENIUS_NITROX_SINGLE = 1
GENIUS_NITROX_MULTI = 2
GENIUS_TRIMIX = 3
GENIUS_GAUGE = 4
GENIUS_FREEDIVE = 5
GENIUS_SCR = 6
GENIUS_OC = 7

DIVEMODE_NAMES = {
    GENIUS_AIR: "oc",
    GENIUS_NITROX_SINGLE: "oc",
    GENIUS_NITROX_MULTI: "oc",
    GENIUS_TRIMIX: "oc",
    GENIUS_GAUGE: "gauge",
    GENIUS_FREEDIVE: "freedive",
    GENIUS_SCR: "scr",
    GENIUS_OC: "oc",
}


def u16le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def s16le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def u32be(data: bytes, offset: int) -> int:
    """Read 32-bit big-endian (used for record type markers)."""
    return struct.unpack_from(">I", data, offset)[0]


def parse_genius_data(data: bytes, header_size: int = 0,
                      interval_ms: int = 5000) -> List[DiveSample]:
    """
    Parsea los datos de muestras de un buceo Genius.

    Sigue la logica de mares_genius_foreach() en mares_iconhd_parser.c:
    - Los record types se leen como big-endian
    - Cada record tiene tamanio fijo que INCLUYE el marker de 4 bytes
    - Los campos de datos empiezan en offset marker=4 desde el inicio del record
    - Depth en 1/10 m, temperature en 1/10 C
    - Cada record termina con una copia del type marker y un CRC16
    """
    samples = []
    size = len(data)
    sample_time_ms = 0

    # Marker offset (data fields start 4 bytes into each record)
    marker = 4

    # Skip the dive header (Genius headersize = 0xB8 + extra + more)
    # The data file for Genius includes the full dive data starting from 0
    # We need to find where records start - skip the header portion
    pos = header_size

    # If header_size is 0, the data file from the ZIP may start directly
    # with the profile records (type+version + records)
    if header_size == 0:
        # Check if file starts with a profile type/version header (4 bytes)
        # then records follow
        if size >= 4:
            # Try to find the first record marker
            # Scan for known markers
            for scan_pos in range(0, min(size - 4, 512)):
                test_type = u32be(data, scan_pos)
                if test_type in (DSTR_TYPE, DPRS_TYPE, TISS_TYPE, DEND_TYPE):
                    pos = scan_pos
                    break

    while pos + 10 <= size:
        # Read record type as big-endian (like libdivecomputer)
        record_type = u32be(data, pos)

        # Determine record length (includes the 4-byte type marker)
        if record_type == DSTR_TYPE:
            length = DSTR_SIZE  # 58
        elif record_type == TISS_TYPE:
            length = TISS_SIZE  # 138
        elif record_type == DPRS_TYPE:
            length = DPRS_SIZE  # 34
        elif record_type == SDPT_TYPE:
            length = SDPT_SIZE  # 78
        elif record_type == AIRS_TYPE:
            length = AIRS_SIZE  # 16
        elif record_type == DEND_TYPE:
            length = DEND_SIZE  # 162
        else:
            # Unknown record, try next byte
            pos += 1
            continue

        if pos + length > size:
            break

        if record_type == DPRS_TYPE:
            # DPRS sample record
            # Fields at offset (pos + marker):
            #   +0: depth (u16le, 1/10 m)
            #   +4: temperature (u16le, 1/10 C)
            #   +0x0A: decotime (u16le)
            #   +0x0C: alarms (u32le)
            #   +0x14: misc (u32le) - contains gasmix, bookmark, deco info
            base = pos + marker

            depth_raw = u16le(data, base + 0)
            depth_m = depth_raw / 10.0

            temp_raw = u16le(data, base + 4)
            temp_c = temp_raw / 10.0

            sample = DiveSample(
                time_seconds=sample_time_ms / 1000.0,
                depth_meters=depth_m,
                temperature_celsius=temp_c,
            )

            # Deco time at +0x0A
            if base + 0x0C <= size:
                decotime_raw = u16le(data, base + 0x0A)
                # Misc at +0x14 for deco stop info
                if base + 0x18 <= size:
                    misc = u32le(data, base + 0x14)
                    decostop = (misc >> 18) & 0x01
                    if decostop:
                        decodepth = (misc >> 19) & 0x7F
                        sample.deco_type = "deco"
                        sample.deco_depth = float(decodepth)
                        sample.deco_time = decotime_raw * 60
                    else:
                        sample.deco_type = "ndl"
                        sample.deco_depth = 0.0
                        sample.deco_time = decotime_raw * 60

            # Alarms at +0x0C
            if base + 0x10 <= size:
                alarms = u32le(data, base + 0x0C)
                if alarms != 0:
                    sample.events.append(f"alarm:0x{alarms:08X}")

            samples.append(sample)
            sample_time_ms += interval_ms

        elif record_type == SDPT_TYPE:
            # SCR sample record
            base = pos + marker
            depth_raw = u16le(data, base + 2)
            depth_m = depth_raw / 10.0
            temp_raw = u16le(data, base + 6)
            temp_c = temp_raw / 10.0

            sample = DiveSample(
                time_seconds=sample_time_ms / 1000.0,
                depth_meters=depth_m,
                temperature_celsius=temp_c,
            )
            samples.append(sample)
            sample_time_ms += interval_ms

        elif record_type == AIRS_TYPE:
            # Air integration record
            base = pos + marker
            pressure_raw = u16le(data, base + 0)
            if samples and pressure_raw > 0 and pressure_raw < 50000:
                samples[-1].pressure_bar = pressure_raw / 100.0
                samples[-1].pressure_tank = 0

        elif record_type == DEND_TYPE:
            # End of dive
            break

        # Skip to next record (length includes the type marker)
        pos += length

    return samples


class DeviceInfo:
    """Informacion del dispositivo extraida de device.info."""
    def __init__(self):
        self.device_name = ""
        self.model = 0
        self.electronic_id = ""
        self.firmware = ""
        self.mac = ""

    @classmethod
    def from_text(cls, text: str) -> "DeviceInfo":
        info = cls()
        for line in text.strip().splitlines():
            line = line.strip()
            if line.startswith("Device:"):
                parts = line.split(":", 1)[1].strip()
                info.device_name = parts.split("(")[0].strip()
                if "(model" in parts:
                    try:
                        info.model = int(parts.split("model")[1].strip().rstrip(")"))
                    except ValueError:
                        pass
            elif line.startswith("Electronic ID:"):
                info.electronic_id = line.split(":", 1)[1].strip()
            elif line.startswith("Firmware:"):
                info.firmware = line.split(":", 1)[1].strip()
            elif line.startswith("MAC:"):
                info.mac = line.split(":", 1)[1].strip()
        return info


def decode_genius_datetime(timestamp: int) -> Tuple[int, int, int, int, int, int]:
    """
    Decodifica un timestamp Genius (32-bit packed):
      bits  0-4:  hour (0-23)
      bits  5-10: minute (0-59)
      bits 11-15: day (1-31)
      bits 16-19: month (1-12)
      bits 20-31: year
    """
    hour   = (timestamp      ) & 0x1F
    minute = (timestamp >>  5) & 0x3F
    day    = (timestamp >> 11) & 0x1F
    month  = (timestamp >> 16) & 0x0F
    year   = (timestamp >> 20) & 0x0FFF
    return year, month, day, hour, minute, 0


def parse_genius_header(header_data: bytes) -> dict:
    """
    Parsea un header Genius (200 bytes) para extraer metadatos del buceo.
    """
    info = {}

    if len(header_data) < 0xB8:
        return info

    # Type and version
    obj_type = u16le(header_data, 0)
    minor = header_data[2]
    major = header_data[3]
    info["obj_version"] = f"{major}.{minor}"

    # Dive number
    info["dive_number"] = u32le(header_data, 4)

    # Datetime at offset 0x08
    timestamp = u32le(header_data, 0x08)
    year, month, day, hour, minute, second = decode_genius_datetime(timestamp)
    info["year"] = year
    info["month"] = month
    info["day"] = day
    info["hour"] = hour
    info["minute"] = minute
    info["second"] = second

    # Settings at offset 0x0C
    settings = u32le(header_data, 0x0C)
    info["mode"] = settings & 0xF

    # Log format
    info["logformat"] = header_data[0x10] if len(header_data) > 0x10 else 0
    extra = 8 if info["logformat"] == 1 else 0

    # Number of samples at offset 0x20 + extra
    if len(header_data) > 0x22 + extra:
        info["nsamples"] = u16le(header_data, 0x20 + extra)

    # Max depth at offset 0x22 + extra (in 1/10 meter)
    if len(header_data) > 0x24 + extra:
        info["maxdepth_raw"] = u16le(header_data, 0x22 + extra)
        info["maxdepth_m"] = info["maxdepth_raw"] / 10.0

    # Avg depth at offset 0x24 + extra
    if len(header_data) > 0x26 + extra:
        info["avgdepth_raw"] = u16le(header_data, 0x24 + extra)
        info["avgdepth_m"] = info["avgdepth_raw"] / 10.0

    # Temperature max at offset 0x26 + extra (in 1/10 C)
    if len(header_data) > 0x28 + extra:
        info["temp_max_raw"] = s16le(header_data, 0x26 + extra)
        info["temp_max_c"] = info["temp_max_raw"] / 10.0

    # Temperature min at offset 0x28 + extra
    if len(header_data) > 0x2A + extra:
        info["temp_min_raw"] = s16le(header_data, 0x28 + extra)
        info["temp_min_c"] = info["temp_min_raw"] / 10.0

    # Atmospheric pressure at offset 0x3E + extra (mbar)
    if len(header_data) > 0x40 + extra:
        info["atmospheric_mbar"] = u16le(header_data, 0x3E + extra)

    # Gas mixes at offset 0x54 + extra (5 slots of 20 bytes each)
    gasmixes = []
    tanks = []
    gasmix_offset = 0x54 + extra
    for i in range(5):
        offset = gasmix_offset + i * 20
        if offset + 12 > len(header_data):
            break
        gasmix_params = u32le(header_data, offset + 0)
        begin_pressure = u16le(header_data, offset + 4)
        end_pressure = u16le(header_data, offset + 6)
        volume = u16le(header_data, offset + 8)
        work_pressure = u16le(header_data, offset + 10)

        o2 = (gasmix_params) & 0x7F
        n2 = (gasmix_params >> 7) & 0x7F
        he = (gasmix_params >> 14) & 0x7F
        state = (gasmix_params >> 21) & 0x03

        if state != 0:  # GASMIX_OFF = 0
            gasmixes.append({
                "oxygen": o2,
                "helium": he,
                "nitrogen": n2,
                "state": state,
            })

        if begin_pressure != 0 or (end_pressure != 0 and end_pressure != 36000):
            tanks.append({
                "volume": volume,
                "workpressure": work_pressure,
                "beginpressure": begin_pressure,
                "endpressure": end_pressure,
            })

    info["gasmixes"] = gasmixes
    info["tanks"] = tanks

    return info





class MaresPuckParser:
    """
    Parser especializado para archivos ZIP de Mares Puck 4 y familia Genius.
    """

    def __init__(self, console: Console):
        self.console = console
        self.device_info: Optional[DeviceInfo] = None

    def can_handle(self, zip_path: str) -> bool:
        """Detecta si el ZIP tiene la estructura Mares Puck/Genius."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                has_device_info = "device.info" in names
                has_headers = any(n.startswith("logbook/header_") for n in names)
                has_data = any(n.startswith("logbook/data_") for n in names)
                return has_device_info and has_headers and has_data
        except (zipfile.BadZipFile, OSError):
            return False

    def parse(self, zip_path: str) -> List[DiveData]:
        """Parsea el ZIP completo y devuelve una lista de DiveData."""
        dives = []

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Parse device info
            if "device.info" in zf.namelist():
                info_text = zf.read("device.info").decode("utf-8", errors="replace")
                self.device_info = DeviceInfo.from_text(info_text)
                self.console.success(
                    f"Dispositivo: {self.device_info.device_name} "
                    f"({self.device_info.electronic_id})"
                )
                if self.device_info.firmware:
                    self.console.detail("Firmware", self.device_info.firmware)

            # Find all header/data pairs
            names = zf.namelist()
            header_files = sorted([n for n in names if n.startswith("logbook/header_")])
            data_files = sorted([n for n in names if n.startswith("logbook/data_")])

            self.console.info(f"Encontrados {len(header_files)} buceos en el logbook")

            for i, header_file in enumerate(header_files):
                # Find matching data file
                idx_str = header_file.split("header_")[1].replace(".bin", "")
                data_file = f"logbook/data_{idx_str}.bin"

                if data_file not in names:
                    self.console.warning(f"Sin datos para {header_file}")
                    continue

                header_data = zf.read(header_file)
                dive_data = zf.read(data_file)

                # Parse header
                header_info = parse_genius_header(header_data)

                if not header_info:
                    self.console.warning(f"No se pudo parsear {header_file}")
                    continue

                # Build DiveData
                dive_num = header_info.get("dive_number", i + 1)

                dive = DiveData(
                    number=dive_num,
                    source_file=f"header_{idx_str}.bin + data_{idx_str}.bin",
                    data_size=len(header_data) + len(dive_data),
                )

                # Datetime
                dive.year = header_info.get("year", 0)
                dive.month = header_info.get("month", 0)
                dive.day = header_info.get("day", 0)
                dive.hour = header_info.get("hour", 0)
                dive.minute = header_info.get("minute", 0)
                dive.second = header_info.get("second", 0)

                # Depths
                dive.maxdepth_meters = header_info.get("maxdepth_m", 0.0)
                dive.avgdepth_meters = header_info.get("avgdepth_m", 0.0)

                # Temperatures
                if "temp_min_c" in header_info:
                    dive.temperature_minimum = header_info["temp_min_c"]
                if "temp_max_c" in header_info:
                    dive.temperature_maximum = header_info["temp_max_c"]

                # Atmospheric pressure
                if "atmospheric_mbar" in header_info:
                    dive.atmospheric_bar = header_info["atmospheric_mbar"] / 1000.0

                # Dive mode
                mode = header_info.get("mode", GENIUS_AIR)
                dive.divemode = DIVEMODE_NAMES.get(mode, "oc")

                # Gas mixes
                for j, gm in enumerate(header_info.get("gasmixes", [])):
                    dive.gasmixes.append(GasMix(
                        index=j,
                        oxygen=float(gm["oxygen"]),
                        helium=float(gm["helium"]),
                        nitrogen=float(gm["nitrogen"]),
                    ))

                # If no gasmix but mode is AIR, add default
                if not dive.gasmixes and mode == GENIUS_AIR:
                    dive.gasmixes.append(GasMix(
                        index=0, oxygen=21.0, helium=0.0, nitrogen=79.0
                    ))

                # Tanks
                for j, t in enumerate(header_info.get("tanks", [])):
                    dive.tanks.append(Tank(
                        gasmix_index=j,
                        volume_liters=float(t["volume"]) / 10.0,
                        workpressure_bar=float(t["workpressure"]) / 100.0,
                        beginpressure_bar=float(t["beginpressure"]) / 100.0,
                        endpressure_bar=float(t["endpressure"]) / 100.0,
                        type="metric",
                    ))

                # Parse sample data
                samples = parse_genius_data(dive_data)
                dive.samples = samples

                # Calculate divetime from samples
                if samples:
                    dive.divetime_seconds = int(samples[-1].time_seconds)

                dives.append(dive)

                self.console.dive_summary(
                    dive.number,
                    dive.format_datetime(),
                    dive.maxdepth_meters,
                    dive.divetime_seconds,
                )

        # Sort by dive number
        dives.sort(key=lambda d: d.number)

        self.console.blank()
        self.console.success(f"Se parsearon {len(dives)} buceos exitosamente")

        return dives
