# Sample Organizer

Aplicación de escritorio para revisar y organizar librerías de samples. El análisis es de solo lectura; la organización copia archivos musicales sin sobrescribir y conserva la ruta original en los informes.

## Desarrollo

Requiere Python 3.12 o posterior.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
sample-organizer
```

La ventana inicia con `~/Music/Samples` como origen y `~/Music/SamplesOrdenados` como destino (relativos a la carpeta personal de cada usuario). No se realiza ninguna operación hasta que el usuario inicia el análisis y confirma la organización.

La eliminación de archivos `.part`, `.lrc` y auxiliares de macOS (`.DS_Store`, `._*` y marcadores relacionados) requiere activar su opción y aceptar una confirmación adicional. Por defecto se conservan. Solo se eliminan esos archivos individuales, nunca carpetas de metadatos o su contenido. Los archivos comprimidos, documentos, presets y formatos desconocidos solo se registran; no se extraen ni se copian.

Las reglas de extensiones y alias editables están en `config/categories.json`. El núcleo de clasificación, escaneo, organización e informes no depende de la GUI.

En los resultados, selecciona un archivo y pulsa **Elegir carpeta para este archivo…** para asignarle una carpeta dentro del destino elegido. Esto permite organizar manualmente los archivos sin clasificar; puedes volver a la ruta calculada con **Usar destino automático**. La elección manual queda registrada en los informes y no modifica el original.

## Empaquetado

Se incluye una especificación para PyInstaller en `packaging/sample-organizer.spec`. Para generar el ejecutable en cada plataforma, instala el extra `package` y ejecuta `pyinstaller --noconfirm packaging/sample-organizer.spec` en el sistema objetivo. La release inicial incluye una app para macOS Intel (x86_64), compilada y probada en macOS.
