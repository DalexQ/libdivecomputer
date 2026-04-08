"""
Clase base abstracta para exportadores de datos de buceo.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ..models import DiveData
from ..console import Console


class BaseExporter(ABC):
    """Clase base para todos los exportadores."""

    def __init__(self, console: Console):
        self.console = console

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Nombre del formato de salida."""
        ...

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Extensión de archivo del formato."""
        ...

    def export(self, dives: List[DiveData], output_dir: str) -> List[str]:
        """
        Exporta los datos de buceo al directorio de salida.

        Args:
            dives: Lista de datos de buceo a exportar.
            output_dir: Directorio donde guardar los archivos.

        Returns:
            Lista de rutas a los archivos generados.
        """
        # Crear directorio si no existe
        os.makedirs(output_dir, exist_ok=True)

        self.console.step(f"Exportando a formato {self.format_name}...")

        try:
            files = self._write(dives, output_dir)

            for f in files:
                name = os.path.basename(f)
                size = os.path.getsize(f)
                self.console.detail(name, self._format_size(size))

            return files

        except (OSError, IOError) as e:
            self.console.error(f"Error escribiendo archivos: {e}")
            return []

    @abstractmethod
    def _write(self, dives: List[DiveData], output_dir: str) -> List[str]:
        """Implementación específica de escritura."""
        ...

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"
