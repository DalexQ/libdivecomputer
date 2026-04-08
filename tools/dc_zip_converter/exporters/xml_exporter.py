"""
Exportador a formato XML.
Genera un archivo XML compatible con el formato de salida de dctool/libdivecomputer.
"""

import os
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent
from typing import List

from ..models import DiveData
from ..console import Console
from .base import BaseExporter


class XmlExporter(BaseExporter):
    """Exporta datos de buceo a formato XML."""

    @property
    def format_name(self) -> str:
        return "XML"

    @property
    def file_extension(self) -> str:
        return ".xml"

    def _write(self, dives: List[DiveData], output_dir: str) -> List[str]:
        files = []

        output_path = os.path.join(output_dir, "dives.xml")

        root = Element("divecomputer")
        root.set("generator", "dc_zip_converter")
        root.set("version", "1.0.0")

        for dive in dives:
            self._write_dive(root, dive)

        tree = ElementTree(root)
        indent(tree, space="  ")

        with open(output_path, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)

        files.append(output_path)
        return files

    def _write_dive(self, parent: Element, dive: DiveData):
        """Escribe un elemento <dive> con todos los datos."""
        dive_el = SubElement(parent, "dive")

        # Número y metadatos
        SubElement(dive_el, "number").text = str(dive.number)
        SubElement(dive_el, "source").text = dive.source_file
        SubElement(dive_el, "size").text = str(dive.data_size)

        # Fingerprint
        if dive.fingerprint:
            SubElement(dive_el, "fingerprint").text = dive.fingerprint

        # Fecha y hora
        datetime_str = dive.format_datetime()
        if datetime_str:
            SubElement(dive_el, "datetime").text = datetime_str

        # Duración
        SubElement(dive_el, "divetime").text = dive.format_divetime()
        SubElement(dive_el, "divetime_seconds").text = str(dive.divetime_seconds)

        # Profundidades
        SubElement(dive_el, "maxdepth").text = f"{dive.maxdepth_meters:.2f}"
        if dive.avgdepth_meters > 0:
            SubElement(dive_el, "avgdepth").text = f"{dive.avgdepth_meters:.2f}"

        # Temperaturas
        if dive.temperature_surface is not None:
            temp = SubElement(dive_el, "temperature")
            temp.set("type", "surface")
            temp.text = f"{dive.temperature_surface:.1f}"
        if dive.temperature_minimum is not None:
            temp = SubElement(dive_el, "temperature")
            temp.set("type", "minimum")
            temp.text = f"{dive.temperature_minimum:.1f}"
        if dive.temperature_maximum is not None:
            temp = SubElement(dive_el, "temperature")
            temp.set("type", "maximum")
            temp.text = f"{dive.temperature_maximum:.1f}"

        # Modo de buceo
        SubElement(dive_el, "divemode").text = dive.divemode

        # Modelo de descompresión
        if dive.decomodel:
            deco = SubElement(dive_el, "decomodel")
            deco.text = dive.decomodel.type
            if dive.decomodel.conservatism:
                deco.set("conservatism", str(dive.decomodel.conservatism))
            if dive.decomodel.type == "buhlmann" and (
                dive.decomodel.gf_low or dive.decomodel.gf_high
            ):
                SubElement(dive_el, "gf").text = (
                    f"{dive.decomodel.gf_low}/{dive.decomodel.gf_high}"
                )

        # Salinidad
        if dive.salinity_type:
            sal = SubElement(dive_el, "salinity")
            sal.text = dive.salinity_type
            if dive.salinity_density:
                sal.set("density", f"{dive.salinity_density:.1f}")

        # Presión atmosférica
        if dive.atmospheric_bar is not None:
            SubElement(dive_el, "atmospheric").text = f"{dive.atmospheric_bar:.5f}"

        # Ubicación
        if dive.location:
            loc = SubElement(dive_el, "location")
            SubElement(loc, "latitude").text = f"{dive.location.latitude:.6f}"
            SubElement(loc, "longitude").text = f"{dive.location.longitude:.6f}"
            SubElement(loc, "altitude").text = f"{dive.location.altitude:.2f}"

        # Mezclas de gases
        for gm in dive.gasmixes:
            gasmix = SubElement(dive_el, "gasmix")
            SubElement(gasmix, "he").text = f"{gm.helium:.1f}"
            SubElement(gasmix, "o2").text = f"{gm.oxygen:.1f}"
            SubElement(gasmix, "n2").text = f"{gm.nitrogen:.1f}"
            if gm.usage != "none":
                SubElement(gasmix, "usage").text = gm.usage

        # Tanques
        for tank in dive.tanks:
            tank_el = SubElement(dive_el, "tank")
            if tank.gasmix_index != 0xFFFFFFFF:
                SubElement(tank_el, "gasmix").text = str(tank.gasmix_index)
            if tank.type != "none":
                SubElement(tank_el, "type").text = tank.type
                SubElement(tank_el, "volume").text = f"{tank.volume_liters:.1f}"
                SubElement(tank_el, "workpressure").text = f"{tank.workpressure_bar:.2f}"
            SubElement(tank_el, "beginpressure").text = f"{tank.beginpressure_bar:.2f}"
            SubElement(tank_el, "endpressure").text = f"{tank.endpressure_bar:.2f}"
            if tank.usage != "none":
                SubElement(tank_el, "usage").text = tank.usage

        # Muestras
        if dive.samples:
            for sample in dive.samples:
                sample_el = SubElement(dive_el, "sample")

                # Tiempo
                total_sec = sample.time_seconds
                minutes = int(total_sec) // 60
                seconds = int(total_sec) % 60
                millis = int((total_sec % 1) * 1000)
                if millis:
                    SubElement(sample_el, "time").text = f"{minutes:02d}:{seconds:02d}.{millis:03d}"
                else:
                    SubElement(sample_el, "time").text = f"{minutes:02d}:{seconds:02d}"

                # Profundidad
                SubElement(sample_el, "depth").text = f"{sample.depth_meters:.2f}"

                # Temperatura
                if sample.temperature_celsius is not None:
                    SubElement(sample_el, "temperature").text = (
                        f"{sample.temperature_celsius:.2f}"
                    )

                # Presión
                if sample.pressure_bar is not None:
                    pressure = SubElement(sample_el, "pressure")
                    pressure.text = f"{sample.pressure_bar:.2f}"
                    if sample.pressure_tank is not None:
                        pressure.set("tank", str(sample.pressure_tank))

                # Heartbeat
                if sample.heartbeat is not None:
                    SubElement(sample_el, "heartbeat").text = str(sample.heartbeat)

                # Setpoint
                if sample.setpoint is not None:
                    SubElement(sample_el, "setpoint").text = f"{sample.setpoint:.2f}"

                # PPO2
                if sample.ppo2 is not None:
                    SubElement(sample_el, "ppo2").text = f"{sample.ppo2:.2f}"

                # CNS
                if sample.cns is not None:
                    SubElement(sample_el, "cns").text = f"{sample.cns:.1f}"

                # Deco
                if sample.deco_type is not None:
                    deco = SubElement(sample_el, "deco")
                    deco.text = sample.deco_type
                    if sample.deco_time is not None:
                        deco.set("time", str(sample.deco_time))
                    if sample.deco_depth is not None:
                        deco.set("depth", f"{sample.deco_depth:.2f}")

                # Gas mix
                if sample.gasmix_index is not None:
                    SubElement(sample_el, "gasmix").text = str(sample.gasmix_index)
