# videoCutter

Herramienta de línea de comandos y GUI para recortar intervalos de un video usando **ffmpeg**. Ejecuta el proyecto con **Python 3.8+ (CPython)**; PyPy no es compatible debido al uso de PySide6 para la interfaz gráfica.

## Requisitos

1. Instala Python 3.8+ desde https://www.python.org/downloads/.
2. Instala ffmpeg y asegúrate de que el comando `ffmpeg` esté disponible en tu `PATH`.
   - Linux: generalmente `sudo apt install ffmpeg`, `sudo pacman -S ffmpeg`, etc.
   - macOS: `brew install ffmpeg`.
   - Windows: descarga desde https://ffmpeg.org/download.html, descomprime y agrega la carpeta `bin` al `PATH`.
3. Crea un entorno virtual con Python 3:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # En PowerShell: .\.venv\Scripts\Activate.ps1
   ```
4. Instala las dependencias:
   ```bash
   python -m pip install -r requirements.txt
   ```

## Uso

### Línea de comandos

El script principal es `video_cutter.py`. No requiere dependencias extra porque solo usa la librería estándar y ejecuta ffmpeg por debajo.

```bash
python video_cutter.py <input> <inicio> <fin> [-o OUTPUT]
```

Ejemplo:

```bash
python video_cutter.py demo.mp4 00:00:05 00:00:12 -o demo_clip.mp4
```

- `<inicio>` y `<fin>` pueden darse en segundos (`12.5`) o en formato `HH:MM:SS(.mmm)`.
- Si omites `-o/--output`, el script generará un nombre automáticamente junto al archivo original.
- El corte intenta copiar los streams (`-c copy`), así que es muy rápido y no re-encodea el video si los codecs lo permiten.

### Interfaz gráfica (PySide6)

La GUI se ejecuta con PySide6 y ofrece vista previa con controles de reproducción y selección visual del intervalo:

```bash
python video_cutter_gui.py
```

Características:

- Selector de archivo con recordatorio de la última sesión.
- Slider doble para marcar inicio y fin, con miniaturas en vivo al arrastrar.
- Reproductor embebido (audio + video) con loop del intervalo antes de cortar.

## Próximos pasos

- Añadir pruebas automáticas y ejemplos adicionales en caso de ampliar la lógica.
- Investigar empaquetado con PyInstaller/Briefcase para distribuir ejecutables nativos.
