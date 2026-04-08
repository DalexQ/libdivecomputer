"""
Entry point para ejecutar dc_zip_converter como módulo.
Permite ejecutar: python -m dc_zip_converter <args>
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
