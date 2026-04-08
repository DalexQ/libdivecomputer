"""
Parser de binarios de computadoras de buceo usando libdivecomputer via ctypes.

Este módulo intenta cargar libdivecomputer dinámicamente. Si la biblioteca no
está disponible, proporciona un parser de respaldo que extrae información
básica de los archivos binarios.
"""

import ctypes
import ctypes.util
import os
import struct
import sys
from pathlib import Path
from typing import List, Optional, Callable

from .models import DiveData, DiveSample, GasMix, Tank, DecoModel, Location
from .console import Console


class ParserError(Exception):
    """Error durante el parseo de binarios."""
    pass


# ─── libdivecomputer ctypes definitions ───

# dc_status_t
DC_STATUS_SUCCESS = 0
DC_STATUS_DONE = 1
DC_STATUS_UNSUPPORTED = -1
DC_STATUS_INVALIDARGS = -2
DC_STATUS_DATAFORMAT = -9

# dc_sample_type_t
DC_SAMPLE_TIME = 0
DC_SAMPLE_DEPTH = 1
DC_SAMPLE_PRESSURE = 2
DC_SAMPLE_TEMPERATURE = 3
DC_SAMPLE_EVENT = 4
DC_SAMPLE_RBT = 5
DC_SAMPLE_HEARTBEAT = 6
DC_SAMPLE_BEARING = 7
DC_SAMPLE_VENDOR = 8
DC_SAMPLE_SETPOINT = 9
DC_SAMPLE_PPO2 = 10
DC_SAMPLE_CNS = 11
DC_SAMPLE_DECO = 12
DC_SAMPLE_GASMIX = 13

# dc_field_type_t
DC_FIELD_DIVETIME = 0
DC_FIELD_MAXDEPTH = 1
DC_FIELD_AVGDEPTH = 2
DC_FIELD_GASMIX_COUNT = 3
DC_FIELD_GASMIX = 4
DC_FIELD_SALINITY = 5
DC_FIELD_ATMOSPHERIC = 6
DC_FIELD_TEMPERATURE_SURFACE = 7
DC_FIELD_TEMPERATURE_MINIMUM = 8
DC_FIELD_TEMPERATURE_MAXIMUM = 9
DC_FIELD_TANK_COUNT = 10
DC_FIELD_TANK = 11
DC_FIELD_DIVEMODE = 12
DC_FIELD_DECOMODEL = 13
DC_FIELD_LOCATION = 14

# Dive modes
DIVEMODE_NAMES = {0: "freedive", 1: "gauge", 2: "oc", 3: "ccr", 4: "scr"}

# Deco types
DECO_NAMES = {0: "ndl", 1: "safety", 2: "deco", 3: "deep"}

# Decomodel types
DECOMODEL_NAMES = {0: "none", 1: "buhlmann", 2: "vpm", 3: "rgbm", 4: "dciem"}

# Tank volume types
TANKVOLUME_NAMES = {0: "none", 1: "metric", 2: "imperial"}

# Usage types
USAGE_NAMES = {0: "none", 1: "oxygen", 2: "diluent", 3: "sidemount"}

DC_GASMIX_UNKNOWN = 0xFFFFFFFF
DC_SENSOR_NONE = 0xFFFFFFFF
DC_TIMEZONE_NONE = -2147483648  # INT_MIN


def _find_libdivecomputer() -> Optional[str]:
    """Busca la biblioteca libdivecomputer en el sistema."""

    # Intentar nombres comunes
    names = []
    if sys.platform == "win32":
        names = ["libdivecomputer.dll", "divecomputer.dll", "libdivecomputer-0.dll"]
    elif sys.platform == "darwin":
        names = ["libdivecomputer.dylib", "libdivecomputer.0.dylib"]
    else:
        names = ["libdivecomputer.so", "libdivecomputer.so.0"]

    # Buscar en directorios comunes relativos al proyecto
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent  # tools/dc_zip_converter -> libdivecomputer root

    search_dirs = [
        project_root / "src" / ".libs",
        project_root / "build" / "src",
        project_root / "build",
        project_root / "lib",
        project_root,
        Path.cwd(),
    ]

    # Añadir paths del sistema
    if sys.platform == "win32":
        search_dirs.extend([
            Path(os.environ.get("PROGRAMFILES", "")) / "libdivecomputer" / "lib",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "libdivecomputer" / "lib",
        ])
    else:
        search_dirs.extend([
            Path("/usr/lib"),
            Path("/usr/local/lib"),
            Path("/usr/lib/x86_64-linux-gnu"),
        ])

    for search_dir in search_dirs:
        for name in names:
            path = search_dir / name
            if path.exists():
                return str(path)

    # Último recurso: find_library del sistema
    result = ctypes.util.find_library("divecomputer")
    return result


class LibDiveComputerParser:
    """
    Parser que usa libdivecomputer via ctypes para parsear binarios
    de computadoras de buceo.
    """

    def __init__(self, console: Console, lib_path: Optional[str] = None,
                 backend: Optional[str] = None, model: int = 0):
        self.console = console
        self.backend = backend
        self.model = model
        self._lib = None
        self._context = None

        # Intentar cargar la biblioteca
        if lib_path:
            path = lib_path
        else:
            path = _find_libdivecomputer()

        if path:
            try:
                self._lib = ctypes.CDLL(path)
                self._setup_bindings()
                self._create_context()
                self.console.success(f"libdivecomputer cargada: {path}")
            except (OSError, AttributeError) as e:
                self.console.warning(f"No se pudo cargar libdivecomputer: {e}")
                self._lib = None
        else:
            self.console.warning(
                "libdivecomputer no encontrada. Usando parser de respaldo."
            )

    @property
    def is_available(self) -> bool:
        return self._lib is not None

    def _setup_bindings(self):
        """Configura los bindings ctypes para libdivecomputer."""
        lib = self._lib

        # Context
        lib.dc_context_new.restype = ctypes.c_int
        lib.dc_context_new.argtypes = [ctypes.POINTER(ctypes.c_void_p)]

        lib.dc_context_free.restype = ctypes.c_int
        lib.dc_context_free.argtypes = [ctypes.c_void_p]

        # Descriptor iterator
        lib.dc_descriptor_iterator_new.restype = ctypes.c_int
        lib.dc_descriptor_iterator_new.argtypes = [
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p
        ]

        lib.dc_iterator_next.restype = ctypes.c_int
        lib.dc_iterator_next.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        lib.dc_iterator_free.restype = ctypes.c_int
        lib.dc_iterator_free.argtypes = [ctypes.c_void_p]

        lib.dc_descriptor_free.argtypes = [ctypes.c_void_p]

        lib.dc_descriptor_get_vendor.restype = ctypes.c_char_p
        lib.dc_descriptor_get_vendor.argtypes = [ctypes.c_void_p]

        lib.dc_descriptor_get_product.restype = ctypes.c_char_p
        lib.dc_descriptor_get_product.argtypes = [ctypes.c_void_p]

        lib.dc_descriptor_get_type.restype = ctypes.c_uint
        lib.dc_descriptor_get_type.argtypes = [ctypes.c_void_p]

        lib.dc_descriptor_get_model.restype = ctypes.c_uint
        lib.dc_descriptor_get_model.argtypes = [ctypes.c_void_p]

        # Parser
        lib.dc_parser_new2.restype = ctypes.c_int
        lib.dc_parser_new2.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),  # parser
            ctypes.c_void_p,                   # context
            ctypes.c_void_p,                   # descriptor
            ctypes.c_char_p,                   # data
            ctypes.c_size_t,                   # size
        ]

        lib.dc_parser_destroy.restype = ctypes.c_int
        lib.dc_parser_destroy.argtypes = [ctypes.c_void_p]

        # Parser get datetime - uses a struct
        lib.dc_parser_get_datetime.restype = ctypes.c_int
        lib.dc_parser_get_datetime.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        # Parser get field
        lib.dc_parser_get_field.restype = ctypes.c_int
        lib.dc_parser_get_field.argtypes = [
            ctypes.c_void_p,  # parser
            ctypes.c_int,     # type
            ctypes.c_uint,    # flags
            ctypes.c_void_p,  # value
        ]

        # Samples foreach
        SAMPLE_CALLBACK = ctypes.CFUNCTYPE(
            None, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p
        )
        lib.dc_parser_samples_foreach.restype = ctypes.c_int
        lib.dc_parser_samples_foreach.argtypes = [
            ctypes.c_void_p,   # parser
            SAMPLE_CALLBACK,   # callback
            ctypes.c_void_p,   # userdata
        ]

        self._SAMPLE_CALLBACK = SAMPLE_CALLBACK

    def _create_context(self):
        """Crea un contexto de libdivecomputer."""
        ctx = ctypes.c_void_p()
        rc = self._lib.dc_context_new(ctypes.byref(ctx))
        if rc != DC_STATUS_SUCCESS:
            raise ParserError(f"Error creando contexto de libdivecomputer: {rc}")
        self._context = ctx

    def _find_descriptor(self, family_name: Optional[str] = None) -> Optional[ctypes.c_void_p]:
        """Busca un descriptor de dispositivo por familia."""
        target = family_name or self.backend
        if not target:
            return None

        iterator = ctypes.c_void_p()
        rc = self._lib.dc_descriptor_iterator_new(
            ctypes.byref(iterator), self._context
        )
        if rc != DC_STATUS_SUCCESS:
            return None

        descriptor = ctypes.c_void_p()
        found = None

        while True:
            rc = self._lib.dc_iterator_next(iterator, ctypes.byref(descriptor))
            if rc != DC_STATUS_SUCCESS:
                break

            vendor = self._lib.dc_descriptor_get_vendor(descriptor)
            product = self._lib.dc_descriptor_get_product(descriptor)

            if vendor and product:
                full_name = f"{vendor.decode()} {product.decode()}"
                if (target.lower() in full_name.lower() or
                    target.lower() in product.decode().lower()):
                    found = descriptor
                    break

            self._lib.dc_descriptor_free(descriptor)
            descriptor = ctypes.c_void_p()

        self._lib.dc_iterator_free(iterator)
        return found

    def parse_file(self, file_path: str, dive_number: int = 1) -> Optional[DiveData]:
        """
        Parsea un archivo binario de dive computer usando libdivecomputer.
        """
        if not self.is_available:
            return None

        # Leer el archivo
        with open(file_path, "rb") as f:
            data = f.read()

        if not data:
            self.console.warning(f"Archivo vacío: {file_path}")
            return None

        # Buscar descriptor
        descriptor = self._find_descriptor()
        if not descriptor:
            self.console.warning(
                f"No se encontró descriptor para backend '{self.backend}'. "
                f"Especifica un backend con --backend."
            )
            return None

        # Crear parser
        parser = ctypes.c_void_p()
        rc = self._lib.dc_parser_new2(
            ctypes.byref(parser),
            self._context,
            descriptor,
            data,
            len(data),
        )

        if rc != DC_STATUS_SUCCESS:
            self.console.debug(f"Error creando parser para {file_path}: rc={rc}")
            return None

        try:
            dive = DiveData(
                number=dive_number,
                source_file=os.path.basename(file_path),
                data_size=len(data),
            )

            # Extraer datetime
            self._parse_datetime(parser, dive)

            # Extraer campos
            self._parse_fields(parser, dive)

            # Extraer samples
            self._parse_samples(parser, dive)

            return dive

        finally:
            self._lib.dc_parser_destroy(parser)

    def _parse_datetime(self, parser, dive: DiveData):
        """Extrae fecha y hora del buceo."""

        # dc_datetime_t struct: year(int), month(int), day(int),
        #                       hour(int), minute(int), second(int),
        #                       timezone(int)
        class DCDatetime(ctypes.Structure):
            _fields_ = [
                ("year", ctypes.c_int),
                ("month", ctypes.c_int),
                ("day", ctypes.c_int),
                ("hour", ctypes.c_int),
                ("minute", ctypes.c_int),
                ("second", ctypes.c_int),
                ("timezone", ctypes.c_int),
            ]

        dt = DCDatetime()
        rc = self._lib.dc_parser_get_datetime(parser, ctypes.byref(dt))
        if rc == DC_STATUS_SUCCESS:
            dive.year = dt.year
            dive.month = dt.month
            dive.day = dt.day
            dive.hour = dt.hour
            dive.minute = dt.minute
            dive.second = dt.second
            if dt.timezone != DC_TIMEZONE_NONE:
                dive.timezone_offset = dt.timezone

    def _parse_fields(self, parser, dive: DiveData):
        """Extrae los campos principales del buceo."""

        # Divetime
        divetime = ctypes.c_uint(0)
        rc = self._lib.dc_parser_get_field(
            parser, DC_FIELD_DIVETIME, 0, ctypes.byref(divetime)
        )
        if rc == DC_STATUS_SUCCESS:
            dive.divetime_seconds = divetime.value

        # Max depth
        maxdepth = ctypes.c_double(0.0)
        rc = self._lib.dc_parser_get_field(
            parser, DC_FIELD_MAXDEPTH, 0, ctypes.byref(maxdepth)
        )
        if rc == DC_STATUS_SUCCESS:
            dive.maxdepth_meters = maxdepth.value

        # Avg depth
        avgdepth = ctypes.c_double(0.0)
        rc = self._lib.dc_parser_get_field(
            parser, DC_FIELD_AVGDEPTH, 0, ctypes.byref(avgdepth)
        )
        if rc == DC_STATUS_SUCCESS:
            dive.avgdepth_meters = avgdepth.value

        # Temperatures
        for field_type, attr in [
            (DC_FIELD_TEMPERATURE_SURFACE, "temperature_surface"),
            (DC_FIELD_TEMPERATURE_MINIMUM, "temperature_minimum"),
            (DC_FIELD_TEMPERATURE_MAXIMUM, "temperature_maximum"),
        ]:
            temp = ctypes.c_double(0.0)
            rc = self._lib.dc_parser_get_field(
                parser, field_type, 0, ctypes.byref(temp)
            )
            if rc == DC_STATUS_SUCCESS:
                setattr(dive, attr, temp.value)

        # Dive mode
        divemode = ctypes.c_uint(2)  # default OC
        rc = self._lib.dc_parser_get_field(
            parser, DC_FIELD_DIVEMODE, 0, ctypes.byref(divemode)
        )
        if rc == DC_STATUS_SUCCESS:
            dive.divemode = DIVEMODE_NAMES.get(divemode.value, "oc")

        # Gas mixes
        ngases = ctypes.c_uint(0)
        rc = self._lib.dc_parser_get_field(
            parser, DC_FIELD_GASMIX_COUNT, 0, ctypes.byref(ngases)
        )
        if rc == DC_STATUS_SUCCESS and ngases.value > 0:
            for i in range(ngases.value):

                class DCGasMix(ctypes.Structure):
                    _fields_ = [
                        ("helium", ctypes.c_double),
                        ("oxygen", ctypes.c_double),
                        ("nitrogen", ctypes.c_double),
                        ("usage", ctypes.c_uint),
                    ]

                gasmix = DCGasMix()
                rc = self._lib.dc_parser_get_field(
                    parser, DC_FIELD_GASMIX, i, ctypes.byref(gasmix)
                )
                if rc == DC_STATUS_SUCCESS:
                    dive.gasmixes.append(GasMix(
                        index=i,
                        helium=gasmix.helium * 100.0,
                        oxygen=gasmix.oxygen * 100.0,
                        nitrogen=gasmix.nitrogen * 100.0,
                        usage=USAGE_NAMES.get(gasmix.usage, "none"),
                    ))

    def _parse_samples(self, parser, dive: DiveData):
        """Extrae las muestras de datos del buceo."""
        samples = []
        current_sample = [None]  # Wrapped in list for closure

        def sample_callback(sample_type, value_ptr, userdata):
            if sample_type == DC_SAMPLE_TIME:
                time_ms = ctypes.cast(value_ptr, ctypes.POINTER(ctypes.c_uint)).contents.value
                if current_sample[0] is not None:
                    samples.append(current_sample[0])
                current_sample[0] = DiveSample(time_seconds=time_ms / 1000.0)

            elif current_sample[0] is not None:
                sample = current_sample[0]
                if sample_type == DC_SAMPLE_DEPTH:
                    sample.depth_meters = ctypes.cast(
                        value_ptr, ctypes.POINTER(ctypes.c_double)
                    ).contents.value
                elif sample_type == DC_SAMPLE_TEMPERATURE:
                    sample.temperature_celsius = ctypes.cast(
                        value_ptr, ctypes.POINTER(ctypes.c_double)
                    ).contents.value
                elif sample_type == DC_SAMPLE_CNS:
                    sample.cns = ctypes.cast(
                        value_ptr, ctypes.POINTER(ctypes.c_double)
                    ).contents.value * 100.0
                elif sample_type == DC_SAMPLE_SETPOINT:
                    sample.setpoint = ctypes.cast(
                        value_ptr, ctypes.POINTER(ctypes.c_double)
                    ).contents.value
                elif sample_type == DC_SAMPLE_GASMIX:
                    sample.gasmix_index = ctypes.cast(
                        value_ptr, ctypes.POINTER(ctypes.c_uint)
                    ).contents.value

        cb = self._SAMPLE_CALLBACK(sample_callback)
        self._lib.dc_parser_samples_foreach(parser, cb, None)

        if current_sample[0] is not None:
            samples.append(current_sample[0])

        dive.samples = samples

    def cleanup(self):
        """Libera los recursos de libdivecomputer."""
        if self._context and self._lib:
            self._lib.dc_context_free(self._context)
            self._context = None


class FallbackParser:
    """
    Parser de respaldo que extrae información básica de archivos binarios
    cuando libdivecomputer no está disponible.

    Soporta análisis heurístico básico de la estructura binaria y proporciona
    metadatos útiles incluso sin la biblioteca nativa.
    """

    def __init__(self, console: Console):
        self.console = console

    def parse_file(self, file_path: str, dive_number: int = 1) -> Optional[DiveData]:
        """
        Parsea un archivo binario extrayendo lo que se pueda de forma heurística.
        """
        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except (OSError, IOError) as e:
            self.console.error(f"No se pudo leer el archivo: {e}")
            return None

        if not data:
            self.console.warning(f"Archivo vacío: {file_path}")
            return None

        file_name = os.path.basename(file_path)

        dive = DiveData(
            number=dive_number,
            source_file=file_name,
            data_size=len(data),
        )

        # Intentar extraer información básica del binario
        self._analyze_binary(data, dive)

        return dive

    def _analyze_binary(self, data: bytes, dive: DiveData):
        """
        Analiza el contenido binario buscando patrones comunes
        de computadoras de buceo.
        """
        size = len(data)

        # Buscar patrones de timestamps (típicamente 4 bytes como epoch o BCD)
        self._try_extract_timestamp(data, dive)

        # Buscar valores de profundidad (típicamente valores de 16 bits en
        # centímetros, almacenados como little-endian)
        depths = self._find_depth_pattern(data)
        if depths:
            dive.maxdepth_meters = max(depths)

            # Generar muestras básicas a partir de los datos de profundidad
            interval = 10  # asumimos intervalo de 10 seg si no se conoce
            for i, depth in enumerate(depths):
                sample = DiveSample(
                    time_seconds=i * interval,
                    depth_meters=depth,
                )
                dive.samples.append(sample)

            if dive.samples:
                dive.divetime_seconds = int(dive.samples[-1].time_seconds)

    def _try_extract_timestamp(self, data: bytes, dive: DiveData):
        """Intenta extraer un timestamp del inicio del archivo."""
        if len(data) < 8:
            return

        # Intentar interpretar los primeros bytes como un timestamp
        # Muchos dive computers almacenan la fecha en los primeros bytes
        # como BCD (Binary Coded Decimal) o como campos separados

        # Patrón 1: año/mes/día/hora/min/seg como bytes individuales
        # (común en Suunto, Mares, etc.)
        if len(data) >= 6:
            year_candidates = []

            # Check offset 0
            for offset in range(0, min(20, len(data) - 5)):
                b = data[offset:offset + 6]

                # Intentar como bytes raw
                year = b[0] + 2000 if b[0] < 100 else b[0]
                month = b[1]
                day = b[2]
                hour = b[3]
                minute = b[4]
                second = b[5]

                if (2000 <= year <= 2030 and 1 <= month <= 12 and
                    1 <= day <= 31 and 0 <= hour <= 23 and
                    0 <= minute <= 59 and 0 <= second <= 59):
                    dive.year = year
                    dive.month = month
                    dive.day = day
                    dive.hour = hour
                    dive.minute = minute
                    dive.second = second
                    return

                # Intentar little-endian 16-bit year
                if offset + 7 <= len(data):
                    year16 = struct.unpack_from("<H", data, offset)[0]
                    if 2000 <= year16 <= 2030:
                        month = data[offset + 2]
                        day = data[offset + 3]
                        hour = data[offset + 4]
                        minute = data[offset + 5]
                        second = data[offset + 6] if offset + 6 < len(data) else 0

                        if (1 <= month <= 12 and 1 <= day <= 31 and
                            0 <= hour <= 23 and 0 <= minute <= 59 and
                            0 <= second <= 59):
                            dive.year = year16
                            dive.month = month
                            dive.day = day
                            dive.hour = hour
                            dive.minute = minute
                            dive.second = second
                            return

    def _find_depth_pattern(self, data: bytes) -> List[float]:
        """
        Busca patrones de datos de profundidad en el binario.
        Los dive computers típicamente almacenan la profundidad como
        valores de 16 bits (en cm o en incrementos de 1/100 bar).
        """
        depths = []

        if len(data) < 20:
            return depths

        # Heurística: buscar secuencias de valores 16-bit LE que parezcan
        # profundidades razonables (0-200 metros, subida y bajada gradual)
        best_offset = -1
        best_count = 0
        best_step = 2  # bytes por muestra

        # Probar diferentes offsets y steps (2, 4, 8 bytes por muestra)
        for step in [2, 4, 8, 12, 16]:
            for start_offset in range(0, min(64, len(data))):
                count = 0
                prev_depth = 0
                valid_sequence = True

                for i in range(20):  # Verificar 20 muestras
                    pos = start_offset + i * step
                    if pos + 2 > len(data):
                        break

                    raw = struct.unpack_from("<H", data, pos)[0]
                    depth_m = raw / 100.0  # Asumir centímetros

                    if 0 <= depth_m <= 200:
                        # Verificar que el cambio no sea abrupto (< 10m por muestra)
                        if i > 0 and abs(depth_m - prev_depth) > 15:
                            valid_sequence = False
                            break
                        count += 1
                        prev_depth = depth_m
                    else:
                        valid_sequence = False
                        break

                if valid_sequence and count > best_count and count >= 5:
                    best_count = count
                    best_offset = start_offset
                    best_step = step

        if best_offset >= 0:
            pos = best_offset
            while pos + 2 <= len(data):
                raw = struct.unpack_from("<H", data, pos)[0]
                depth_m = raw / 100.0
                if depth_m > 200:
                    break
                depths.append(depth_m)
                pos += best_step

        return depths


class DiveParser:
    """
    Fachada que selecciona automáticamente el parser adecuado
    (libdivecomputer o fallback).
    """

    def __init__(self, console: Console, lib_path: Optional[str] = None,
                 backend: Optional[str] = None, model: int = 0):
        self.console = console
        self._ldc_parser = None
        self._fallback = FallbackParser(console)

        # Intentar con libdivecomputer
        if backend:
            self._ldc_parser = LibDiveComputerParser(
                console, lib_path=lib_path, backend=backend, model=model
            )
            if not self._ldc_parser.is_available:
                self._ldc_parser = None
        else:
            # Intentar cargar de todos modos
            self._ldc_parser = LibDiveComputerParser(console, lib_path=lib_path)
            if not self._ldc_parser.is_available:
                self._ldc_parser = None

        if not self._ldc_parser:
            self.console.info(
                "Usando parser de respaldo (análisis heurístico).\n"
                "    Para obtener mejores resultados, compila libdivecomputer\n"
                "    y especifica --backend <familia> --lib <ruta_dll>"
            )

    @property
    def using_native(self) -> bool:
        return self._ldc_parser is not None

    def parse_files(self, file_paths: List[str]) -> List[DiveData]:
        """Parsea una lista de archivos binarios."""
        dives = []
        total = len(file_paths)

        self.console.section("Parseando archivos binarios")

        for i, file_path in enumerate(file_paths, 1):
            file_name = os.path.basename(file_path)
            self.console.step(f"Procesando [{i}/{total}]: {file_name}")

            dive = None

            # Intentar con libdivecomputer primero
            if self._ldc_parser:
                dive = self._ldc_parser.parse_file(file_path, dive_number=i)

            # Si falla, usar fallback
            if dive is None:
                dive = self._fallback.parse_file(file_path, dive_number=i)

            if dive:
                dives.append(dive)
                self.console.dive_summary(
                    dive.number,
                    dive.format_datetime(),
                    dive.maxdepth_meters,
                    dive.divetime_seconds,
                )
            else:
                self.console.warning(f"No se pudo parsear: {file_name}")

        self.console.blank()
        self.console.success(
            f"Se parsearon {len(dives)} de {total} archivo(s) exitosamente"
        )

        return dives

    def cleanup(self):
        """Libera recursos."""
        if self._ldc_parser:
            self._ldc_parser.cleanup()
