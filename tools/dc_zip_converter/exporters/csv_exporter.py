"""
Exportador a formato CSV.
Genera un archivo resumen y archivos individuales con las muestras de cada buceo.
"""

import csv
import os
from typing import List

from ..models import DiveData
from ..console import Console
from .base import BaseExporter


class CsvExporter(BaseExporter):
    """Exporta datos de buceo a formato CSV."""

    @property
    def format_name(self) -> str:
        return "CSV"

    @property
    def file_extension(self) -> str:
        return ".csv"

    def _write(self, dives: List[DiveData], output_dir: str) -> List[str]:
        files = []

        # 1. Archivo resumen con todos los buceos
        summary_path = os.path.join(output_dir, "dives_summary.csv")
        self._write_summary(dives, summary_path)
        files.append(summary_path)

        # 2. Archivos individuales de muestras por cada buceo con datos
        samples_dir = os.path.join(output_dir, "samples")
        for dive in dives:
            if dive.samples:
                os.makedirs(samples_dir, exist_ok=True)
                sample_path = os.path.join(
                    samples_dir, f"dive_{dive.number:03d}_samples.csv"
                )
                self._write_samples(dive, sample_path)
                files.append(sample_path)

        # 3. Archivo de mezclas de gases (si hay)
        gasmixes_data = [(d, gm) for d in dives for gm in d.gasmixes]
        if gasmixes_data:
            gasmix_path = os.path.join(output_dir, "gasmixes.csv")
            self._write_gasmixes(dives, gasmix_path)
            files.append(gasmix_path)

        return files

    def _write_summary(self, dives: List[DiveData], path: str):
        """Escribe el archivo resumen de todos los buceos."""
        if not dives:
            return

        fieldnames = [
            "dive_number", "source_file", "datetime",
            "divetime_minutes", "maxdepth_meters", "avgdepth_meters",
            "temp_surface_c", "temp_min_c", "temp_max_c",
            "divemode", "gasmix_count", "sample_count",
            "data_size_bytes", "fingerprint",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for dive in dives:
                writer.writerow(dive.to_summary_csv_row())

    def _write_samples(self, dive: DiveData, path: str):
        """Escribe las muestras de un buceo individual."""
        if not dive.samples:
            return

        fieldnames = [
            "time_seconds", "depth_meters", "temperature_celsius",
            "pressure_bar", "heartbeat", "ppo2", "cns",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for sample in dive.samples:
                writer.writerow(sample.to_csv_row())

    def _write_gasmixes(self, dives: List[DiveData], path: str):
        """Escribe las mezclas de gases de todos los buceos."""
        fieldnames = [
            "dive_number", "gasmix_index",
            "helium_pct", "oxygen_pct", "nitrogen_pct", "usage",
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for dive in dives:
                for gm in dive.gasmixes:
                    row = gm.to_dict()
                    row["dive_number"] = dive.number
                    row["gasmix_index"] = gm.index
                    writer.writerow(row)
