# dc_zip_converter 🤿

Herramienta de línea de comandos para procesar archivos ZIP con datos binarios
extraídos de computadoras de buceo. Convierte los datos a formatos
estructurados como CSV, JSON o XML.

## Características

- ✅ Descomprime y valida archivos `.zip`
- ✅ Detecta automáticamente archivos binarios de computadoras de buceo
- ✅ Parseo nativo via `libdivecomputer` (si está compilada)
- ✅ Parser heurístico de respaldo cuando la biblioteca nativa no está disponible
- ✅ Exportación a **CSV**, **JSON** y **XML**
- ✅ Mensajes claros y con colores en la consola
- ✅ Manejo robusto de errores
- ✅ Diseño modular y extensible

## Requisitos

- Python 3.8 o superior
- No requiere dependencias externas (solo biblioteca estándar)
- **Opcional**: `libdivecomputer` compilada como `.dll`/`.so` para parseo nativo

## Uso

### Comando básico

```bash
python -m dc_zip_converter datos_buceo.zip
```

### Especificar formato de salida

```bash
python -m dc_zip_converter datos_buceo.zip --format csv
python -m dc_zip_converter datos_buceo.zip --format json
python -m dc_zip_converter datos_buceo.zip --format xml
```

### Especificar directorio de salida

```bash
python -m dc_zip_converter datos_buceo.zip --output ./mis_resultados
```

### Uso con libdivecomputer (parseo nativo)

```bash
# Especificando el backend de la computadora de buceo
python -m dc_zip_converter datos.zip --backend petrel --format json

# Especificando también la ruta a la biblioteca
python -m dc_zip_converter datos.zip --backend petrel --lib /usr/local/lib/libdivecomputer.so

# Con modelo específico
python -m dc_zip_converter datos.zip --backend atom2 --model 0x4342
```

### Opciones completas

```
uso: dc_zip_converter [-h] [-f {csv,json,xml}] [-o OUTPUT]
                      [-b BACKEND] [--lib LIB] [--model MODEL]
                      [-v] [--no-color] [--version]
                      zip_path

argumentos posicionales:
  zip_path              Ruta al archivo .zip con los binarios

opciones:
  -h, --help            Mostrar ayuda
  -f, --format          Formato de salida: csv, json, xml (default: json)
  -o, --output          Directorio de salida
  -b, --backend         Backend/familia de la computadora de buceo
  --lib                 Ruta a la biblioteca libdivecomputer
  --model               Número de modelo del dispositivo
  -v, --verbose         Mensajes de depuración detallados
  --no-color            Desactivar colores en la salida
  --version             Mostrar versión
```

## Backends soportados

La herramienta soporta todas las familias de computadoras de buceo de libdivecomputer:

| Fabricante | Backends |
|---|---|
| Suunto | `solution`, `eon`, `vyper`, `vyper2`, `d9`, `eonsteel` |
| Uwatec/Scubapro | `aladin`, `memomouse`, `smart` |
| Oceanic | `vtpro`, `veo250`, `atom2`, `i330r` |
| Mares | `nemo`, `puck`, `darwin`, `iconhd` |
| Heinrichs Weikamp | `ostc`, `frog`, `ostc3` |
| Cressi | `edy`, `leonardo`, `goa` |
| Shearwater | `predator`, `petrel` |
| Atomic Aquatics | `cobalt` |
| Reefnet | `sensus`, `sensuspro`, `sensusultra` |
| Otros | `n2ition3`, `nitekq`, `aqualand`, `idive`, `cochran`, ... |

## Formatos de salida

### CSV
Genera múltiples archivos:
- `dives_summary.csv` - Resumen de todos los buceos
- `samples/dive_NNN_samples.csv` - Muestras de cada buceo
- `gasmixes.csv` - Mezclas de gases utilizadas

### JSON
Genera:
- `dives.json` - Datos completos con todas las muestras
- `dives_summary.json` - Resumen sin muestras (más compacto)

### XML
Genera:
- `dives.xml` - Formato compatible con libdivecomputer/Subsurface

## Arquitectura

```
dc_zip_converter/
├── __init__.py          # Package init
├── __main__.py          # Entry point (python -m)
├── cli.py               # Interfaz de línea de comandos
├── console.py           # Salida formateada por consola
├── models.py            # Modelos de datos (dataclasses)
├── zip_handler.py       # Validación y extracción de ZIP
├── binary_parser.py     # Parseo de binarios (ctypes + fallback)
└── exporters/
    ├── __init__.py
    ├── base.py           # Clase base abstracta
    ├── csv_exporter.py   # Exportador CSV
    ├── json_exporter.py  # Exportador JSON
    └── xml_exporter.py   # Exportador XML
```

## Extender

Para agregar un nuevo formato de salida:

1. Crear una nueva clase que herede de `BaseExporter` en `exporters/`
2. Implementar los métodos `format_name`, `file_extension` y `_write`
3. Registrar el exportador en `cli.py` → `get_exporter()`
