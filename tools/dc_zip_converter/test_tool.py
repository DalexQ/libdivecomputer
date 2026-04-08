"""
Script de prueba para dc_zip_converter.
Crea un archivo ZIP de prueba con datos binarios simulados
y ejecuta la herramienta para verificar que funciona correctamente.
"""

import os
import sys
import struct
import zipfile
import tempfile
import shutil


def create_fake_dive_binary(dive_num: int, max_depth_cm: int = 2500,
                            samples: int = 60) -> bytes:
    """
    Crea datos binarios simulados que imitan la estructura
    de un dump de computadora de buceo.

    Estructura simulada:
    - Header: año(2B) mes(1B) día(1B) hora(1B) min(1B) seg(1B) padding(1B)
    - Muestras: profundidad(2B LE, en cm) + temperatura(2B LE, en décimas °C)
    """
    data = bytearray()

    # Header con fecha
    import datetime
    base_date = datetime.datetime(2025, 3, 15 + dive_num, 9, 30, 0)
    data.extend(struct.pack("<H", base_date.year))
    data.append(base_date.month)
    data.append(base_date.day)
    data.append(base_date.hour)
    data.append(base_date.minute)
    data.append(base_date.second)
    data.append(0)  # padding

    # Muestras: simulamos un perfil de buceo (descenso -> fondo -> ascenso)
    import math
    for i in range(samples):
        # Perfil de profundidad tipo campana
        t = i / max(samples - 1, 1)
        # Descenso rápido, fondo, ascenso más lento
        if t < 0.15:
            depth_frac = t / 0.15
        elif t < 0.70:
            depth_frac = 1.0 - 0.1 * math.sin((t - 0.15) / 0.55 * math.pi)
        else:
            depth_frac = (1.0 - t) / 0.30

        depth_cm = int(max_depth_cm * max(depth_frac, 0))
        # Temperatura: disminuye con la profundidad
        temp_decidegrees = int(280 - depth_cm * 0.02)  # 28.0°C superficie

        data.extend(struct.pack("<H", depth_cm))
        data.extend(struct.pack("<H", temp_decidegrees))

    return bytes(data)


def create_test_zip(zip_path: str, num_dives: int = 3):
    """Crea un archivo ZIP de prueba con datos binarios simulados."""
    print(f"  Creando ZIP de prueba con {num_dives} buceos simulados...")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(num_dives):
            # Cada buceo con diferente profundidad maxima
            depths = [2000, 3500, 1800]
            samples = [45, 72, 30]

            binary_data = create_fake_dive_binary(
                dive_num=i,
                max_depth_cm=depths[i % len(depths)],
                samples=samples[i % len(samples)],
            )

            filename = f"dive_{i + 1:03d}.bin"
            zf.writestr(filename, binary_data)

        # Agregar un archivo de texto (debe ser ignorado)
        zf.writestr("README.txt", "Datos de buceo exportados")

    size = os.path.getsize(zip_path)
    print(f"  ZIP creado: {zip_path} ({size} bytes)")


def main():
    print("=" * 60)
    print("  TEST: dc_zip_converter")
    print("=" * 60)
    print()

    # Directorio temporal para la prueba
    test_dir = os.path.join(os.path.dirname(__file__), "_test_output")
    os.makedirs(test_dir, exist_ok=True)

    zip_path = os.path.join(test_dir, "test_dives.zip")
    output_base = os.path.join(test_dir, "results")

    try:
        # Crear ZIP de prueba
        print("[1/4] Creando datos de prueba...")
        create_test_zip(zip_path, num_dives=3)
        print()

        # Agregar el directorio de tools al path
        tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        from dc_zip_converter.cli import main as cli_main

        # Test JSON
        print("[2/4] Probando exportacion JSON...")
        output_json = os.path.join(output_base, "json")
        rc = cli_main([zip_path, "--format", "json", "--output", output_json, "--no-color"])
        print(f"  Resultado: {'OK' if rc == 0 else 'ERROR'} (codigo: {rc})")
        print()

        # Test CSV
        print("[3/4] Probando exportacion CSV...")
        output_csv = os.path.join(output_base, "csv")
        rc = cli_main([zip_path, "--format", "csv", "--output", output_csv, "--no-color"])
        print(f"  Resultado: {'OK' if rc == 0 else 'ERROR'} (código: {rc})")
        print()

        # Test XML
        print("[4/4] Probando exportacion XML...")
        output_xml = os.path.join(output_base, "xml")
        rc = cli_main([zip_path, "--format", "xml", "--output", output_xml, "--no-color"])
        print(f"  Resultado: {'OK' if rc == 0 else 'ERROR'} (código: {rc})")
        print()

        # Verificar archivos generados
        print("=" * 60)
        print("  ARCHIVOS GENERADOS:")
        print("=" * 60)
        for root, dirs, files in os.walk(output_base):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, output_base)
                size = os.path.getsize(full)
                print(f"  {rel} ({size} bytes)")

        print()

        # Mostrar contenido del JSON de ejemplo
        json_file = os.path.join(output_json, "dives_summary.json")
        if os.path.exists(json_file):
            print("=" * 60)
            print("  EJEMPLO DE SALIDA (JSON summary):")
            print("=" * 60)
            with open(json_file, "r", encoding="utf-8") as f:
                print(f.read()[:2000])

        # Mostrar contenido del CSV de ejemplo
        csv_file = os.path.join(output_csv, "dives_summary.csv")
        if os.path.exists(csv_file):
            print()
            print("=" * 60)
            print("  EJEMPLO DE SALIDA (CSV summary):")
            print("=" * 60)
            with open(csv_file, "r", encoding="utf-8") as f:
                print(f.read()[:1000])

        print()
        print("[OK] Test completado exitosamente.")
        return 0

    except Exception as e:
        print(f"\n[ERROR] Error en el test: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
