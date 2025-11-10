#!/usr/bin/env python3
"""
Cross-platform CLI helper to trim segments from video files using ffmpeg.

The script only depends on the standard library so it runs seamlessly on CPython
and PyPy. Make sure ffmpeg is installed and available on PATH before using it.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple


def parse_timestamp(value: str) -> float:
    """
    Accepts timestamps as seconds (float/int) or as HH:MM:SS(.mmm) and
    returns their value in seconds.
    """
    value = value.strip()
    if not value:
        raise ValueError("empty timestamp")

    if ":" not in value:
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"Invalid seconds value '{value}'") from exc

    parts = value.split(":")
    if len(parts) > 3:
        raise ValueError(
            f"Invalid timestamp '{value}'. Use SS, MM:SS or HH:MM:SS formats."
        )

    hours, minutes, seconds = 0.0, 0.0, 0.0
    parts = [float(p) for p in parts]
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        minutes, seconds = parts
    else:
        seconds = parts[0]

    return hours * 3600 + minutes * 60 + seconds


def format_timestamp(seconds: float) -> str:
    """Return timestamp formatted as HH:MM:SS.mmm for ffmpeg."""
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs = remainder / 1000
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def build_output_path(input_path: Path, suffix: str) -> Path:
    stem = input_path.stem
    return input_path.with_name(f"{stem}_{suffix}{input_path.suffix}")


def ensure_ffmpeg_available() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError(
            "ffmpeg no está instalado o no se encuentra en PATH. "
            "Instálalo desde https://ffmpeg.org/download.html y vuelve a intentarlo."
        )
    return ffmpeg_path


def build_command(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    start_ts: str,
    end_ts: str,
) -> Tuple[str, ...]:
    # Use stream copy (-c copy) to avoid re-encoding when possible.
    return (
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        start_ts,
        "-to",
        end_ts,
        "-i",
        str(input_file),
        "-c",
        "copy",
        str(output_file),
    )


def cut_video(input_file: Path, start: str, end: str, output: Path | None) -> Path:
    ffmpeg_path = ensure_ffmpeg_available()

    start_seconds = parse_timestamp(start)
    end_seconds = parse_timestamp(end)

    if start_seconds < 0 or end_seconds < 0:
        raise ValueError("Los tiempos deben ser mayores o iguales a 0.")
    if end_seconds <= start_seconds:
        raise ValueError("El tiempo final debe ser mayor que el inicial.")

    formatted_start = format_timestamp(start_seconds)
    formatted_end = format_timestamp(end_seconds)

    if output is None:
        suffix = f"{int(start_seconds)}s_{int(end_seconds)}s"
        output = build_output_path(input_file, suffix)

    command = build_command(
        ffmpeg_path, input_file, output, formatted_start, formatted_end
    )

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "ffmpeg no pudo generar el recorte. "
            "Revisa que el video y los timestamps sean válidos."
        ) from exc

    return output


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Genera un recorte de video entre los segundos especificados usando ffmpeg. "
            "Acepta tiempos en segundos (e.g. 12.5) o en formato HH:MM:SS."
        )
    )
    parser.add_argument(
        "input",
        help="Ruta al archivo de video de entrada",
    )
    parser.add_argument(
        "start",
        help="Segundo inicial (por ejemplo 10, 00:00:10 o 00:00:10.500)",
    )
    parser.add_argument(
        "end",
        help="Segundo final (debe ser mayor al inicial)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Ruta del archivo de salida. Si se omite se generará automáticamente.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    input_file = Path(args.input).expanduser()
    if not input_file.is_file():
        parser.error(f"El archivo de entrada '{input_file}' no existe.")

    output_file = Path(args.output).expanduser() if args.output else None
    try:
        result = cut_video(input_file, args.start, args.end, output_file)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    print(f"Video generado en: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
