# videoCutter

Herramienta de línea de comandos para recortar intervalos de un video usando **ffmpeg**. El proyecto está pensado para ejecutarse con **PyPy 3**, aprovechando su compilación JIT para tener mejor rendimiento en tiempo real.

## Requisitos

1. Instala PyPy 3 más reciente desde https://www.pypy.org.
2. Instala ffmpeg y asegúrate de que el comando `ffmpeg` esté disponible en tu `PATH`.
   - Linux: generalmente `sudo apt install ffmpeg`, `sudo pacman -S ffmpeg`, etc.
   - macOS: `brew install ffmpeg`.
   - Windows: descarga desde https://ffmpeg.org/download.html, descomprime y agrega la carpeta `bin` al `PATH`.
3. Crea un entorno virtual con PyPy:
   ```bash
   pypy3 -m venv .venv
   source .venv/bin/activate   # En PowerShell: .\.venv\Scripts\Activate.ps1
   ```
4. Instala las dependencias (solo estándar por ahora):
   ```bash
   pypy3 -m pip install -r requirements.txt
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

### Interfaz gráfica

También cuentas con una interfaz simple construida con Tkinter que funciona tanto en Windows como en Linux:

```bash
python video_cutter_gui.py
```

La ventana te permitirá:

- Seleccionar el archivo de video mediante un diálogo del sistema.
- Ingresar el tiempo de inicio y final en los mismos formatos aceptados por la CLI.
- Ejecutar el recorte; el resultado se guardará junto al archivo original con un nombre generado automáticamente.

## Próximos pasos

- Añadir pruebas automáticas y ejemplos adicionales en caso de ampliar la lógica.
- Investigar empaquetado con PyInstaller/Briefcase para distribuir ejecutables nativos.
