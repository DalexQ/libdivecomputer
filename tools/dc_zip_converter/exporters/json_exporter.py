"""
Exportador a formato JSON.
Genera un único archivo JSON con todos los datos de buceo estructurados.
"""

import json
import os
from typing import List

from ..models import DiveData
from ..console import Console
from .base import BaseExporter


class JsonExporter(BaseExporter):
    """Exporta datos de buceo a formato JSON."""

    @property
    def format_name(self) -> str:
        return "JSON"

    @property
    def file_extension(self) -> str:
        return ".json"

    def _write(self, dives: List[DiveData], output_dir: str) -> List[str]:
        files = []

        # Archivo principal con todos los datos
        output_path = os.path.join(output_dir, "dives.json")

        data = {
            "metadata": {
                "generator": "dc_zip_converter",
                "version": "1.0.0",
                "total_dives": len(dives),
                "format": "libdivecomputer-json",
            },
            "dives": [dive.to_dict() for dive in dives],
        }

        # Calcular estadísticas agregadas
        if dives:
            data["statistics"] = self._compute_statistics(dives)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        files.append(output_path)

        # Opcionalmente, generar un archivo resumen compacto (sin samples)
        summary_path = os.path.join(output_dir, "dives_summary.json")
        summary_data = {
            "metadata": data["metadata"],
            "dives": [],
        }
        for dive in dives:
            d = dive.to_dict()
            d.pop("samples", None)  # Remover samples para el resumen
            summary_data["dives"].append(d)

        if dives:
            summary_data["statistics"] = data.get("statistics", {})

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)

        files.append(summary_path)

        return files

    def _compute_statistics(self, dives: List[DiveData]) -> dict:
        """Calcula estadísticas agregadas de todos los buceos."""
        depths = [d.maxdepth_meters for d in dives if d.maxdepth_meters > 0]
        times = [d.divetime_seconds for d in dives if d.divetime_seconds > 0]
        temps_min = [d.temperature_minimum for d in dives if d.temperature_minimum is not None]
        temps_max = [d.temperature_maximum for d in dives if d.temperature_maximum is not None]

        stats = {}

        if depths:
            stats["depth"] = {
                "max_meters": round(max(depths), 2),
                "min_meters": round(min(depths), 2),
                "avg_meters": round(sum(depths) / len(depths), 2),
            }

        if times:
            total_seconds = sum(times)
            stats["time"] = {
                "total_seconds": total_seconds,
                "total_formatted": f"{total_seconds // 3600}h {(total_seconds % 3600) // 60}m",
                "avg_minutes": round(sum(times) / len(times) / 60.0, 1),
                "max_minutes": round(max(times) / 60.0, 1),
                "min_minutes": round(min(times) / 60.0, 1),
            }

        if temps_min or temps_max:
            all_temps = temps_min + temps_max
            stats["temperature"] = {
                "min_celsius": round(min(all_temps), 1),
                "max_celsius": round(max(all_temps), 1),
            }

        # Conteo de modos de buceo
        mode_counts = {}
        for d in dives:
            mode_counts[d.divemode] = mode_counts.get(d.divemode, 0) + 1
        stats["dive_modes"] = mode_counts

        return stats
