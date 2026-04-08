"""
Manejo de archivos ZIP: validación, descompresión y extracción de binarios.
"""

import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple

from .console import Console


class ZipHandlerError(Exception):
    """Error durante el manejo del archivo ZIP."""
    pass


class ZipHandler:
    """Maneja la descompresión y validación de archivos ZIP con datos de buceo."""

    # Extensiones comúnmente encontradas en dumps de dive computers
    BINARY_EXTENSIONS = {
        ".bin", ".dat", ".raw", ".dump", ".dmp", ".log",
        ".dive", ".dlf", ".sde", ".fit",
    }

    # Extensiones a ignorar
    IGNORE_EXTENSIONS = {
        ".txt", ".md", ".readme", ".pdf", ".doc", ".docx",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp",
        ".ds_store", ".thumbs.db",
    }

    IGNORE_PREFIXES = {"__MACOSX", "."}

    def __init__(self, console: Console):
        self.console = console
        self._temp_dir = None

    def validate(self, zip_path: str) -> Path:
        """
        Valida que el archivo existe y es un ZIP válido.

        Returns:
            Path al archivo ZIP validado.

        Raises:
            ZipHandlerError: si el archivo no existe, no es .zip, o está corrupto.
        """
        path = Path(zip_path)

        # Verificar que el archivo existe
        if not path.exists():
            raise ZipHandlerError(f"El archivo no existe: {path}")

        # Verificar que es un archivo (no un directorio)
        if not path.is_file():
            raise ZipHandlerError(f"La ruta no es un archivo: {path}")

        # Verificar extensión
        if path.suffix.lower() != ".zip":
            raise ZipHandlerError(
                f"El archivo no tiene extensión .zip: {path.suffix}\n"
                f"  Archivo recibido: {path.name}"
            )

        # Verificar que es un ZIP válido
        if not zipfile.is_zipfile(path):
            raise ZipHandlerError(
                f"El archivo no es un ZIP válido o está corrupto: {path.name}"
            )

        # Intentar abrir para verificar integridad
        try:
            with zipfile.ZipFile(path, "r") as zf:
                corrupt = zf.testzip()
                if corrupt is not None:
                    raise ZipHandlerError(
                        f"El archivo ZIP contiene datos corruptos.\n"
                        f"  Primer archivo corrupto: {corrupt}"
                    )
        except zipfile.BadZipFile as e:
            raise ZipHandlerError(f"Archivo ZIP corrupto: {e}")

        self.console.success(f"Archivo ZIP válido: {path.name}")
        return path

    def extract(self, zip_path: Path) -> Tuple[str, List[str]]:
        """
        Extrae los archivos binarios del ZIP a un directorio temporal.

        Returns:
            Tupla (directorio_temporal, lista_de_archivos_binarios)

        Raises:
            ZipHandlerError: si no se pueden extraer los archivos.
        """
        self.console.step("Descomprimiendo archivo ZIP...")

        try:
            self._temp_dir = tempfile.mkdtemp(prefix="dc_zip_")

            with zipfile.ZipFile(zip_path, "r") as zf:
                all_files = zf.namelist()
                self.console.detail("Archivos en ZIP", str(len(all_files)))

                # Filtrar archivos
                binary_files = []
                skipped = []

                for file_name in all_files:
                    # Ignorar directorios
                    if file_name.endswith("/"):
                        continue

                    # Ignorar archivos del sistema
                    base_name = os.path.basename(file_name)
                    if any(file_name.startswith(p) for p in self.IGNORE_PREFIXES):
                        skipped.append(file_name)
                        continue
                    if base_name.startswith("."):
                        skipped.append(file_name)
                        continue

                    # Verificar extensión
                    ext = Path(file_name).suffix.lower()
                    if ext in self.IGNORE_EXTENSIONS:
                        skipped.append(file_name)
                        continue

                    # Extraer el archivo
                    zf.extract(file_name, self._temp_dir)
                    full_path = os.path.join(self._temp_dir, file_name)

                    # Si tiene extensión binaria conocida, o no tiene extensión
                    # (lo cual es común en dumps de dive computers), incluirlo
                    if ext in self.BINARY_EXTENSIONS or ext == "" or self._is_binary_file(full_path):
                        binary_files.append(full_path)
                    else:
                        # Incluir de todos modos, el parser determinará si es válido
                        binary_files.append(full_path)

                # Reportar resultados
                if skipped:
                    self.console.debug(f"Archivos ignorados: {len(skipped)}")

                if not binary_files:
                    raise ZipHandlerError(
                        "No se encontraron archivos binarios en el ZIP.\n"
                        f"  El ZIP contiene {len(all_files)} archivo(s), "
                        f"pero ninguno parece ser un binario de dive computer."
                    )

                self.console.success(
                    f"Se extrajeron {len(binary_files)} archivo(s) binario(s)"
                )

                for bf in binary_files:
                    name = os.path.basename(bf)
                    size = os.path.getsize(bf)
                    self.console.detail(name, self._format_size(size))

                return self._temp_dir, binary_files

        except zipfile.BadZipFile as e:
            raise ZipHandlerError(f"Error leyendo el ZIP: {e}")
        except PermissionError as e:
            raise ZipHandlerError(f"Permisos insuficientes: {e}")
        except OSError as e:
            raise ZipHandlerError(f"Error del sistema de archivos: {e}")

    def cleanup(self):
        """Limpia el directorio temporal."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
                self.console.debug(f"Directorio temporal eliminado: {self._temp_dir}")
            except OSError:
                pass  # Best effort

    @staticmethod
    def _is_binary_file(file_path: str, check_bytes: int = 8192) -> bool:
        """Detecta si un archivo es binario leyendo los primeros bytes."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(check_bytes)
            # Si contiene bytes nulos, probablemente es binario
            if b"\x00" in chunk:
                return True
            # Si más del 30% de bytes no son ASCII imprimible, es binario
            text_chars = set(range(32, 127)) | {9, 10, 13}  # printable + tab/newline/cr
            non_text = sum(1 for byte in chunk if byte not in text_chars)
            return non_text / len(chunk) > 0.3 if chunk else False
        except (OSError, IOError):
            return False

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Formatea un tamaño en bytes a una cadena legible."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
