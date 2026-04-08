"""
Interfaz de línea de comandos (CLI) para dc_zip_converter.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List

from . import __version__
from .console import Console
from .zip_handler import ZipHandler, ZipHandlerError
from .binary_parser import DiveParser, ParserError
from .exporters.csv_exporter import CsvExporter
from .exporters.json_exporter import JsonExporter
from .exporters.xml_exporter import XmlExporter


# Backends soportados por libdivecomputer
SUPPORTED_BACKENDS = [
    "solution", "eon", "vyper", "vyper2", "d9", "eonsteel",
    "aladin", "memomouse", "smart",
    "sensus", "sensuspro", "sensusultra",
    "vtpro", "veo250", "atom2", "i330r",
    "nemo", "puck", "darwin", "iconhd",
    "ostc", "frog", "ostc3",
    "edy", "leonardo", "goa",
    "n2ition3", "cobalt",
    "predator", "petrel",
    "nitekq", "aqualand", "idive",
    "cochran", "divecomputereu", "extreme",
    "lynx", "sp2", "excursion", "screen",
    "cosmiq", "s1", "freedom", "symbios",
]

SUPPORTED_FORMATS = ["csv", "json", "xml"]

DEFAULT_OUTPUT_DIR = "output_buceo"


def create_parser() -> argparse.ArgumentParser:
    """Crea el parser de argumentos de línea de comandos."""

    parser = argparse.ArgumentParser(
        prog="dc_zip_converter",
        description=(
            "🤿 Herramienta de conversión de datos de computadoras de buceo.\n"
            "   Procesa archivos ZIP con binarios extraídos de computadoras de buceo\n"
            "   y exporta los datos a CSV, JSON o XML."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos de uso:\n"
            "  python -m dc_zip_converter datos_buceo.zip\n"
            "  python -m dc_zip_converter datos.zip --format json\n"
            "  python -m dc_zip_converter datos.zip --format csv --output ./resultados\n"
            "  python -m dc_zip_converter datos.zip --backend petrel --format xml\n"
            "\n"
            "Backends soportados (computadoras de buceo):\n"
            f"  {', '.join(SUPPORTED_BACKENDS[:15])},\n"
            f"  {', '.join(SUPPORTED_BACKENDS[15:30])},\n"
            f"  {', '.join(SUPPORTED_BACKENDS[30:])}\n"
            "\n"
            "Nota: Si libdivecomputer no está compilada en el sistema,\n"
            "se usará un parser de respaldo con funcionalidad limitada."
        ),
    )

    # Argumento posicional: ruta al ZIP
    parser.add_argument(
        "zip_path",
        type=str,
        help="Ruta al archivo .zip con los binarios de la computadora de buceo.",
    )

    # Formato de salida
    parser.add_argument(
        "-f", "--format",
        type=str,
        choices=SUPPORTED_FORMATS,
        default="json",
        help="Formato de salida (default: json).",
    )

    # Directorio de salida
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help=f"Directorio de salida (default: ./{DEFAULT_OUTPUT_DIR}).",
    )

    # Backend (familia de computadora de buceo)
    parser.add_argument(
        "-b", "--backend",
        type=str,
        choices=SUPPORTED_BACKENDS,
        default=None,
        help="Backend/familia de la computadora de buceo (necesario para parser nativo).",
    )

    # Ruta a la biblioteca libdivecomputer
    parser.add_argument(
        "--lib",
        type=str,
        default=None,
        help="Ruta a la biblioteca libdivecomputer (.dll/.so/.dylib).",
    )

    # Modelo del dispositivo
    parser.add_argument(
        "--model",
        type=int,
        default=0,
        help="Número de modelo del dispositivo (default: 0).",
    )

    # Modo verbose
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostrar mensajes de depuración detallados.",
    )

    # Sin colores
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Desactivar salida con colores.",
    )

    # Version
    parser.add_argument(
        "--version",
        action="version",
        version=f"dc_zip_converter {__version__}",
    )

    return parser


def get_exporter(format_name: str, console: Console):
    """Retorna el exportador adecuado según el formato."""
    exporters = {
        "csv": CsvExporter,
        "json": JsonExporter,
        "xml": XmlExporter,
    }
    exporter_class = exporters.get(format_name)
    if not exporter_class:
        raise ValueError(f"Formato no soportado: {format_name}")
    return exporter_class(console)


def main(argv: List[str] = None) -> int:
    """
    Punto de entrada principal de la aplicación.

    Returns:
        Código de salida (0 = éxito, 1 = error).
    """
    arg_parser = create_parser()
    args = arg_parser.parse_args(argv)

    # Inicializar consola
    console = Console(verbose=args.verbose, no_color=args.no_color)

    # Banner
    console.header("dc_zip_converter v" + __version__)

    start_time = time.time()
    zip_handler = None
    dive_parser = None

    try:
        # ── Paso 1: Validar el archivo ZIP ──
        console.section("Validacion del archivo ZIP")
        zip_handler = ZipHandler(console)
        zip_path = zip_handler.validate(args.zip_path)

        # ── Paso 2: Detectar formato y parsear ──
        # Intentar detectar formato Mares Puck/Genius automaticamente
        from .mares_parser import MaresPuckParser

        mares_parser = MaresPuckParser(console)
        parser_name = None
        dives = []

        if mares_parser.can_handle(str(zip_path)):
            console.section("Dispositivo Mares detectado")
            dives = mares_parser.parse(str(zip_path))
            parser_name = "Mares Puck/Genius (nativo)"
        else:
            # Flujo generico: extraer y parsear con el parser general
            console.section("Extraccion de archivos")
            temp_dir, binary_files = zip_handler.extract(zip_path)

            console.section("Inicializando parser")
            dive_parser = DiveParser(
                console,
                lib_path=args.lib,
                backend=args.backend,
                model=args.model,
            )

            dives = dive_parser.parse_files(binary_files)
            parser_name = "libdivecomputer (nativo)" if dive_parser.using_native else "Heuristico (respaldo)"

        if not dives:
            console.error("No se pudieron parsear datos de buceo de los archivos.")
            console.info(
                "Posibles causas:\n"
                "    - Los archivos no son binarios validos de computadora de buceo\n"
                "    - Falta especificar el backend correcto con --backend\n"
                "    - libdivecomputer no esta disponible para parseo nativo"
            )
            return 1

        # ── Paso 3: Exportar ──
        console.section("Exportacion de datos")

        # Determinar directorio de salida
        output_dir = args.output or DEFAULT_OUTPUT_DIR
        output_dir = os.path.abspath(output_dir)

        console.detail("Formato", args.format.upper())
        console.detail("Directorio", output_dir)

        exporter = get_exporter(args.format, console)
        generated_files = exporter.export(dives, output_dir)

        if not generated_files:
            console.error("No se generaron archivos de salida.")
            return 1

        # ── Resumen final ──
        elapsed = time.time() - start_time
        console.section("Resumen")
        console.success(f"Proceso completado en {elapsed:.2f} segundos")
        console.detail("Buceos procesados", str(len(dives)))
        console.detail("Archivos generados", str(len(generated_files)))
        console.detail("Directorio de salida", output_dir)
        console.detail("Parser", parser_name)

        if parser_name and "respaldo" in parser_name.lower():
            console.warning(
                "Para obtener resultados mas precisos, compila libdivecomputer\n"
                "      y usa: --backend <familia> --lib <ruta_dll>"
            )

        console.blank()

        return 0

    except ZipHandlerError as e:
        console.error(f"Error con el archivo ZIP:\n    {e}")
        return 1

    except ParserError as e:
        console.error(f"Error del parser:\n    {e}")
        return 1

    except KeyboardInterrupt:
        console.warning("Proceso interrumpido por el usuario.")
        return 130

    except Exception as e:
        console.error(f"Error inesperado: {type(e).__name__}: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    finally:
        # Limpieza
        if zip_handler:
            zip_handler.cleanup()
        if dive_parser:
            dive_parser.cleanup()
