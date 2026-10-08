# Teclado Científico: cómo publicar la web con las 3 descargas

Contenido de esta carpeta:

- `teclado_griego.py`: la aplicación (Windows, Mac y Linux).
- `.github/workflows/compilar.yml`: compila las 3 versiones de forma automática en GitHub.
- `index.html`: la página web de descargas.

## Pasos (una sola vez)

1. **Cree una cuenta en github.com** (gratis) y un repositorio **público**, por ejemplo `teclado-griego`.
2. **Suba el contenido de esta carpeta** al repositorio. En la página del repositorio: *Add file > Upload files*, y arrastre `teclado_griego.py`, `index.html`, `LEEME.md` y la carpeta `.github` completa.
   - Si la carpeta `.github` no se sube, use *Add file > Create new file*, escriba el nombre `.github/workflows/compilar.yml` y pegue el contenido del archivo.
3. **Edite `index.html`** (ícono del lápiz en GitHub) y cambie la línea
   `const REPO = "TU_USUARIO/TU_REPO";` por su usuario y repositorio, por ejemplo `"julian/teclado-griego"`.
4. **Genere las descargas:** vaya a *Releases > Draft a new release*, en *Choose a tag* escriba `v1.0` y elija *Create new tag*, y luego *Publish release*.
5. **Espere unos 5 minutos** y revise la pestaña *Actions*: deben aparecer tres tareas en verde (Windows, macOS, Linux). Al terminar, los tres archivos quedan adjuntos en el release.
6. **Active la web:** *Settings > Pages > Build and deployment > Deploy from a branch*, rama `main`, carpeta `/ (root)`, *Save*. En un par de minutos la web queda en
   `https://SU_USUARIO.github.io/teclado-griego/`.

Ese enlace es el que puede compartir.

## Para actualizar el programa

Modifique `teclado_griego.py`, cree un nuevo release con otra etiqueta (`v1.1`) y los botones de la web descargan automáticamente la última versión.

## Uso del teclado

- **Escribir:** haga clic en un símbolo y se escribe donde esté el cursor. Al pasar el mouse por encima, la barra superior muestra su nombre.
- **Recientes:** la fila de arriba repite los últimos 9 símbolos usados.
- **Modo compacto:** el botón `▴` deja solo la barra y la fila de recientes; `▾` lo expande (elegir una pestaña también lo expande).
- **Ocultar y mostrar:** con el atajo **Ctrl+Alt+G** (solo Windows y Linux con X11). Si el teclado no aparece, pruebe el atajo: puede estar oculto.
- **Si no puede escribir** (por ejemplo, en un programa que se ejecuta como administrador), el teclado lo avisa y copia el símbolo para pegarlo con Ctrl+V.

### Cambiar el atajo

El programa guarda su configuración en un archivo `config.json`:

- Windows: `%APPDATA%\TecladoCientifico\config.json`
- Mac: `~/Library/Application Support/TecladoCientifico/config.json`
- Linux: `~/.config/TecladoCientifico/config.json`

Con el programa cerrado, edite la línea `"atajo"`. Formato: modificadores (`ctrl`, `alt`, `shift`, `win`) más una letra, número o tecla F1 a F12, unidos con `+`; por ejemplo `"ctrl+shift+k"` o `"ctrl+alt+f9"`. Con `""` el atajo queda desactivado.

## Importante

- La versión de Windows es la más probable que funcione sin ajustes. Las de Mac y Linux no pudieron probarse y deben considerarse en prueba.
- Si una de las tres compilaciones falla, las otras igualmente se publican.
- Mac: la aplicación se compila para chips M1 o posteriores. En Mac con procesador Intel no funcionará.
- Linux: solo funciona en X11; en Wayland el sistema suele bloquear la escritura en otras aplicaciones.
- Puede usar también Vercel o Netlify para alojar `index.html`, pero GitHub Pages es la opción más simple porque todo queda en un solo lugar.
