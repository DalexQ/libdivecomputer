"""
Utilidades de salida por consola con colores y formato.
"""

import io
import os
import sys


def _safe_print(*args, **kwargs):
    """Print que maneja errores de encoding en Windows (cp1252)."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback: reemplazar caracteres no soportados
        file = kwargs.get("file", sys.stdout)
        end = kwargs.get("end", "\n")
        text = " ".join(str(a) for a in args)
        text = text.encode(file.encoding or "utf-8", errors="replace").decode(
            file.encoding or "utf-8", errors="replace"
        )
        print(text, end=end, file=file, flush=kwargs.get("flush", False))


def _supports_unicode() -> bool:
    """Detecta si la consola soporta Unicode."""
    try:
        encoding = sys.stdout.encoding or ""
        return encoding.lower() in ("utf-8", "utf8", "utf_8", "cp65001")
    except Exception:
        return False


class Console:
    """Manejo de salida formateada por consola."""

    # ANSI color codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"

    def __init__(self, verbose: bool = False, no_color: bool = False):
        self.verbose = verbose
        self.no_color = no_color or not sys.stdout.isatty()
        self._unicode = _supports_unicode()

        # Symbols: ASCII fallback para consolas que no soportan Unicode
        if self._unicode:
            self.CHECK = "\u2713"
            self.CROSS = "\u2717"
            self.ARROW = "\u2192"
            self.BULLET = "\u2022"
            self.WARN = "\u26a0"
            self.INFO = "i"
            self.DIVE = "*"
            self.BOX_TL = "\u2554"
            self.BOX_TR = "\u2557"
            self.BOX_BL = "\u255a"
            self.BOX_BR = "\u255d"
            self.BOX_H = "\u2550"
            self.BOX_V = "\u2551"
            self.LINE_H = "\u2500"
            self.BAR_FULL = "\u2588"
            self.BAR_EMPTY = "\u2591"
        else:
            self.CHECK = "[OK]"
            self.CROSS = "[X]"
            self.ARROW = "->"
            self.BULLET = "*"
            self.WARN = "[!]"
            self.INFO = "[i]"
            self.DIVE = "[D]"
            self.BOX_TL = "+"
            self.BOX_TR = "+"
            self.BOX_BL = "+"
            self.BOX_BR = "+"
            self.BOX_H = "="
            self.BOX_V = "|"
            self.LINE_H = "-"
            self.BAR_FULL = "#"
            self.BAR_EMPTY = "."

    def _c(self, color: str, text: str) -> str:
        """Aplica color al texto si el terminal lo soporta."""
        if self.no_color:
            return text
        return f"{color}{text}{self.RESET}"

    def header(self, text: str):
        """Muestra un encabezado prominente."""
        line = self.BOX_H * (len(text) + 4)
        _safe_print()
        _safe_print(self._c(self.CYAN + self.BOLD, f"{self.BOX_TL}{line}{self.BOX_TR}"))
        _safe_print(self._c(self.CYAN + self.BOLD, f"{self.BOX_V}  {text}  {self.BOX_V}"))
        _safe_print(self._c(self.CYAN + self.BOLD, f"{self.BOX_BL}{line}{self.BOX_BR}"))
        _safe_print()

    def section(self, text: str):
        """Muestra un titulo de seccion."""
        _safe_print(self._c(self.BLUE + self.BOLD, f"\n{self.LINE_H}{self.LINE_H} {text} {self.LINE_H}{self.LINE_H}"))

    def info(self, text: str):
        """Muestra un mensaje informativo."""
        _safe_print(self._c(self.CYAN, f"  {self.INFO} {text}"))

    def success(self, text: str):
        """Muestra un mensaje de exito."""
        _safe_print(self._c(self.GREEN, f"  {self.CHECK} {text}"))

    def warning(self, text: str):
        """Muestra una advertencia."""
        _safe_print(self._c(self.YELLOW, f"  {self.WARN} {text}"))

    def error(self, text: str):
        """Muestra un error."""
        _safe_print(self._c(self.RED + self.BOLD, f"  {self.CROSS} {text}"), file=sys.stderr)

    def step(self, text: str):
        """Muestra un paso del proceso."""
        _safe_print(self._c(self.WHITE, f"  {self.ARROW} {text}"))

    def detail(self, label: str, value: str):
        """Muestra un detalle con etiqueta y valor."""
        _safe_print(f"    {self._c(self.DIM, label + ':')} {value}")

    def progress(self, current: int, total: int, label: str = ""):
        """Muestra una barra de progreso simple."""
        width = 30
        filled = int(width * current / total) if total > 0 else 0
        bar = self.BAR_FULL * filled + self.BAR_EMPTY * (width - filled)
        pct = (current / total * 100) if total > 0 else 0
        line = f"\r  {self._c(self.CYAN, bar)} {pct:5.1f}% ({current}/{total})"
        if label:
            line += f" {label}"
        _safe_print(line, end="", flush=True)
        if current >= total:
            _safe_print()  # newline al final

    def dive_summary(self, number: int, datetime_str: str, depth: float, duration_s: int):
        """Muestra un resumen compacto de un buceo."""
        dur = f"{duration_s // 60}:{duration_s % 60:02d}"
        _safe_print(
            f"    {self._c(self.BOLD, f'{self.DIVE} Buceo #{number:03d}')}  "
            f"{self._c(self.DIM, datetime_str)}  "
            f"Profundidad: {self._c(self.CYAN, f'{depth:.1f}m')}  "
            f"Duracion: {self._c(self.GREEN, dur)}"
        )

    def debug(self, text: str):
        """Muestra un mensaje de debug (solo en modo verbose)."""
        if self.verbose:
            _safe_print(self._c(self.DIM, f"  [DEBUG] {text}"))

    def separator(self):
        """Muestra un separador visual."""
        _safe_print(self._c(self.DIM, "  " + self.LINE_H * 50))

    def blank(self):
        """Linea en blanco."""
        _safe_print()
