#!/usr/bin/env python3
"""
Demostracion en vivo del clasificador SERB v1.

Uso (desde la raiz del proyecto, env `serb`):
    python demo/demo_webcam.py                    # camara 0 + galeria demo/galeria/
    python demo/demo_webcam.py --carpeta fotos/   # galeria en otra carpeta
    python demo/demo_webcam.py --camara 1         # otra camara (o ruta a video)

Camara y galeria conviven en la misma sesion; se cambia con C y G sin
reiniciar. Si la camara no abre (p. ej. WSL sin usbipd) la demo arranca en
galeria y lo indica en pantalla; C vuelve a intentar abrirla.

Teclas:
    C        modo camara
    G        modo galeria
    ESPACIO  captura y clasifica (modo camara)
    <- / ->  imagen anterior / siguiente (modo galeria; tambien A / D)
    F        pantalla completa
    ESC / Q  salir

Modo camara: al pulsar ESPACIO se toman --frames frames seguidos (5 por
defecto), se promedian sus vectores de probabilidad (test-time ensembling) y
se decide sobre el promedio. Cada frame llega a Predictor como PIL RGB sin
recomprimir y pasa por el mismo reducir() (LANCZOS 256 + JPEG q90) que las
imagenes de calibracion. Ver CLAUDE.md, limitacion 1.

Modo galeria: cada imagen se clasifica una vez por la ruta de archivo, que es
exactamente la ruta calibrada; no hay promedio.

Las reglas de decision (umbral, corte de riesgo, regla del mas severo) viven
en scripts/predecir.py; este archivo solo presenta el resultado.
"""
import argparse, sys, time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from scripts.predecir import (Predictor, AVISO_GENERAL, UMBRAL, CORTE_RIESGO,  # noqa: E402
                              MODELO_VERSION)

# --------------------------------------------------------------------------
# Disposicion de la ventana (pixeles del lienzo; la ventana es redimensionable)
W, H = 1600, 900
PIE = 56                     # franja inferior del aviso (una sola linea)
PANEL = 620                  # panel lateral derecho
VID_W, VID_H = W - PANEL, H - PIE
M = 30                       # margen interior del panel

EXTS = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".tif", ".tiff"}
GALERIA_DEFECTO = RAIZ / "demo" / "galeria"

# Colores RGB. Alto contraste: fondo casi negro, texto blanco.
FONDO = (12, 12, 12)
FONDO_PANEL = (24, 24, 24)
TEXTO = (255, 255, 255)
TENUE = (165, 165, 165)
GRIS_NOID = (105, 105, 105)
NARANJA = (255, 150, 0)

# nivel -> (color de banda, color de texto sobre la banda, rotulo)
BANDA = {
    "segura":      ((40, 190, 80),  (0, 0, 0),       "SEGURA"),
    "irritante":   ((255, 205, 0),  (0, 0, 0),       "IRRITANTE"),
    "desconocida": ((255, 205, 0),  (0, 0, 0),       "DESCONOCIDA"),
    "toxica":      ((215, 30, 30),  (255, 255, 255), "TÓXICA"),
    "letal":       ((150, 0, 0),    (255, 255, 255), "LETAL"),
}
# color del rotulo de riesgo en los renglones del top-3 (texto sobre fondo oscuro)
COLOR_RIESGO_TXT = {"segura": (70, 215, 105), "irritante": (255, 205, 0),
                    "desconocida": (255, 205, 0), "toxica": (255, 80, 80),
                    "letal": (255, 60, 60)}
RIESGO_TXT = {"segura": "segura", "irritante": "irritante", "desconocida": "desconocida",
              "toxica": "tóxica", "letal": "letal"}

TECLAS_IZQ = {65361, 2424832, 0x1000012, ord("a"), ord("A")}
TECLAS_DER = {65363, 2555904, 0x1000014, ord("d"), ord("D")}
TECLAS_SALIR = {27, ord("q"), ord("Q")}
TECLAS_CAMARA = {ord("c"), ord("C")}
TECLAS_GALERIA = {ord("g"), ord("G")}
TECLAS_COMPLETA = {ord("f"), ord("F")}
ESPACIO = 32

# --------------------------------------------------------------------------
# Fuentes

_FUENTES = {}
_RUTAS_FUENTE = {
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
           "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf"],
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:/Windows/Fonts/arial.ttf", "/Library/Fonts/Arial.ttf"],
}


def fuente(tam, negrita=False):
    clave = (tam, negrita)
    if clave not in _FUENTES:
        for ruta in _RUTAS_FUENTE[negrita]:
            if Path(ruta).exists():
                _FUENTES[clave] = ImageFont.truetype(ruta, tam)
                break
        else:
            _FUENTES[clave] = ImageFont.load_default(size=tam)
    return _FUENTES[clave]


def ancho(d, txt, f):
    return d.textlength(txt, font=f)


def ajustar(d, txt, max_w, tam, negrita=True, minimo=20):
    """Fuente mas grande (<= tam) con la que txt cabe en max_w."""
    while tam > minimo and ancho(d, txt, fuente(tam, negrita)) > max_w:
        tam -= 2
    return fuente(tam, negrita)


def envolver(d, txt, f, max_w):
    lineas, actual = [], ""
    for pal in txt.split():
        prueba = f"{actual} {pal}".strip()
        if ancho(d, prueba, f) <= max_w or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = pal
    if actual:
        lineas.append(actual)
    return lineas


def nombre_legible(clase):
    n = clase.replace("_", " ")
    return n + "." if n.endswith(" spp") else n


def pct(v):
    return f"{v * 100:.0f} %"


# --------------------------------------------------------------------------
# Panel lateral

def dibujar_panel(estado):
    """estado: {"tipo": espera|analizando|resultado|error, "resultado": dict,
    "mensaje": str, "nota": str}. Devuelve PIL RGB de PANEL x VID_H."""
    im = Image.new("RGB", (PANEL, VID_H), FONDO_PANEL)
    d = ImageDraw.Draw(im)
    iw = PANEL - 2 * M
    d.text((M, 22), f"SERB · Flora de Jalisco · {MODELO_VERSION}", font=fuente(22), fill=TENUE)

    tipo = estado["tipo"]
    r = estado.get("resultado")
    by, bh = 62, 196            # banda de riesgo

    # ---- banda -----------------------------------------------------------
    if tipo == "resultado" and r["identificada"]:
        nivel = r["riesgo"] if r["riesgo"] in BANDA else "desconocida"
        color, ctxt, rotulo = BANDA[nivel]
        sub = r.get("aviso") or ""
        cabeza = "RIESGO"
    elif tipo == "resultado":
        color, ctxt, rotulo = GRIS_NOID, TEXTO, "NO IDENTIFICADA"
        sub = "Riesgo desconocido. No la consuma ni la manipule sin protección."
        cabeza = "RESULTADO"
    elif tipo == "analizando":
        color, ctxt, rotulo = (55, 55, 55), TEXTO, "ANALIZANDO…"
        sub, cabeza = estado.get("mensaje", ""), ""
    elif tipo == "error":
        color, ctxt, rotulo = (55, 55, 55), TEXTO, "ERROR"
        sub, cabeza = estado.get("mensaje", ""), ""
    else:
        color, ctxt, rotulo = (55, 55, 55), TEXTO, estado.get("rotulo", "SIN CAPTURA")
        sub, cabeza = estado.get("mensaje", ""), ""

    d.rectangle([M, by, PANEL - M, by + bh], fill=color)
    if cabeza:
        d.text((M + 20, by + 12), cabeza, font=fuente(24, True), fill=ctxt)
    f = ajustar(d, rotulo, iw - 40, 68)
    d.text((M + 20, by + 40), rotulo, font=f, fill=ctxt)
    fs = fuente(22)
    for k, linea in enumerate(envolver(d, sub, fs, iw - 40)[:3]):
        d.text((M + 20, by + 124 + k * 26), linea, font=fs, fill=ctxt)

    y = by + bh + 8
    if tipo == "resultado" and r["identificada"] and r.get("riesgo_origen") != r["identificacion"]:
        n = next(k for k, c in enumerate(r["top3"], 1) if c["clase"] == r["riesgo_origen"])
        txt = f"Riesgo elevado por el candidato {n}: {nombre_legible(r['riesgo_origen'])}"
        d.text((M, y), txt, font=ajustar(d, txt, iw, 22, False, 14), fill=NARANJA)

    if tipo != "resultado":
        return im

    # ---- identificacion ----------------------------------------------------
    y = 300
    d.text((M, y), "IDENTIFICACIÓN", font=fuente(22, True), fill=TENUE)
    if r["identificada"]:
        nom = nombre_legible(r["identificacion"])
        d.text((M, y + 28), nom, font=ajustar(d, nom, iw, 46), fill=TEXTO)
    else:
        d.text((M, y + 28), "—", font=fuente(46, True), fill=TENUE)

    # ---- confianza ---------------------------------------------------------
    y = 392
    conf, umb = r["confianza"], r["umbral"]
    d.text((M, y), "CONFIANZA", font=fuente(22, True), fill=TENUE)
    porimg = r.get("confianza_por_imagen")
    if porimg and len(porimg) > 1:
        t = f"promedio de {len(porimg)} frames (cada uno: {pct(min(porimg))} – {pct(max(porimg))})"
        d.text((M + ancho(d, "CONFIANZA", fuente(22, True)) + 16, y + 2), t,
               font=ajustar(d, t, iw - 170, 20, False, 14), fill=TENUE)
    fv = fuente(46, True)
    d.text((M, y + 26), pct(conf), font=fv, fill=TEXTO)
    if abs(conf - umb) < 0.05:
        d.text((M + ancho(d, pct(conf), fv) + 24, y + 42), "CERCA DEL UMBRAL",
               font=fuente(26, True), fill=NARANJA)
    bx, bw, bt, bb = M, iw, y + 88, y + 118
    d.rectangle([bx, bt, bx + bw, bb], fill=(55, 55, 55))
    d.rectangle([bx, bt, bx + int(bw * conf), bb],
                fill=(235, 235, 235) if conf >= umb else (125, 125, 125))
    ux = bx + int(bw * umb)
    d.rectangle([ux - 2, bt - 8, ux + 2, bb + 8], fill=NARANJA)
    fu = fuente(20)
    d.text((min(ux - 40, bx + bw - 120), bb + 10), f"umbral {pct(umb)}", font=fu, fill=NARANJA)

    # ---- top-3 -------------------------------------------------------------
    y = 556
    d.text((M, y), "CANDIDATOS (TOP-3)", font=fuente(22, True), fill=TENUE)
    if not r["identificada"]:
        msg = "Sin candidatos: la confianza está bajo el umbral."
        for k, linea in enumerate(envolver(d, msg, fuente(24), iw)):
            d.text((M, y + 34 + k * 30), linea, font=fuente(24), fill=TENUE)
        return im
    fp, fr = fuente(28, True), fuente(20, True)
    col_p = ancho(d, "100 %", fp)            # columna fija de porcentaje
    x_riesgo = PANEL - M - col_p - 16         # borde derecho de la columna de riesgo
    alguno_fuera = False
    for k, c in enumerate(r["top3"]):
        ry = y + 32 + k * 48
        cuenta = c["cuenta_para_riesgo"]
        alguno_fuera |= not cuenta
        col = TEXTO if cuenta else TENUE
        p_txt = pct(c["confianza"]) if c["confianza"] >= 0.01 else "<1 %"
        pw = ancho(d, p_txt, fp)
        rtxt = RIESGO_TXT.get(c["riesgo"], "desconocida") + ("" if cuenta else " *")
        rw = ancho(d, rtxt, fr)
        nom = f"{k + 1}. {nombre_legible(c['clase'])}"
        d.text((M, ry), nom, font=ajustar(d, nom, x_riesgo - rw - 20 - M, 28, False, 16), fill=col)
        d.text((x_riesgo - rw, ry + 6), rtxt, font=fr,
               fill=COLOR_RIESGO_TXT.get(c["riesgo"], TENUE) if cuenta else TENUE)
        d.text((PANEL - M - pw, ry), p_txt, font=fp, fill=col)
    if alguno_fuera:
        d.text((M, y + 32 + 3 * 48 + 2),
               f"* bajo el corte de {pct(r['corte_riesgo'])}: no cuenta para el riesgo",
               font=fuente(18), fill=TENUE)
    return im


# --------------------------------------------------------------------------
# Pie con el aviso (estatico)

def dibujar_pie():
    """Una sola linea, peso normal y tono tenue: debe leerse, no competir con
    el resultado. Solo el rotulo "Aviso:" va resaltado."""
    im = Image.new("RGB", (W, PIE), (18, 18, 18))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 3], fill=(255, 205, 0))
    rot = "Aviso: "
    tam = 20
    while tam > 12 and (ancho(d, rot, fuente(tam, True))
                        + ancho(d, AVISO_GENERAL, fuente(tam))) > W - 60:
        tam -= 1
    fr, ft = fuente(tam, True), fuente(tam)
    total = ancho(d, rot, fr) + ancho(d, AVISO_GENERAL, ft)
    x, y = (W - total) // 2, 3 + (PIE - 3) // 2
    d.text((x, y), rot, font=fr, fill=(255, 205, 0), anchor="lm")
    d.text((x + ancho(d, rot, fr), y), AVISO_GENERAL, font=ft, fill=(205, 205, 205), anchor="lm")
    return im


# --------------------------------------------------------------------------
# Zona de video

def encajar(rgb):
    """Escala un frame RGB (ndarray) para caber en VID_W x VID_H. Devuelve
    (imagen PIL, x0, y0, escala)."""
    h, w = rgb.shape[:2]
    s = min(VID_W / w, VID_H / h)
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    im = Image.fromarray(cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA))
    return im, (VID_W - nw) // 2, (VID_H - nh) // 2, s


def guia_modelo(d, x0, y0, nw, nh):
    """Recuadro de lo que ve el modelo: reducir() lleva el lado corto a 256 y
    CenterCrop(224) toma el centro -> cuadrado de 224/256 del lado corto."""
    lado = min(nw, nh) * 224 / 256
    cx, cy = x0 + nw / 2, y0 + nh / 2
    a, b = (cx - lado / 2, cy - lado / 2), (cx + lado / 2, cy + lado / 2)
    L = lado * 0.12
    for (px, py), (sx, sy) in (((a[0], a[1]), (1, 1)), ((b[0], a[1]), (-1, 1)),
                               ((a[0], b[1]), (1, -1)), ((b[0], b[1]), (-1, -1))):
        d.line([(px, py), (px + sx * L, py)], fill=TEXTO, width=4)
        d.line([(px, py), (px, py + sy * L)], fill=TEXTO, width=4)


def etiqueta(d, xy, txt, tam=24, color=TEXTO):
    f = fuente(tam, True)
    x, y = xy
    d.rectangle([x - 10, y - 6, x + ancho(d, txt, f) + 10, y + tam + 10], fill=(0, 0, 0))
    d.text((x, y), txt, font=f, fill=color)


def componer(rgb, panel, pie, ayuda, info=None, miniatura=None, alerta=None):
    lienzo = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(lienzo)
    if rgb is not None:
        im, x0, y0, _ = encajar(rgb)
        lienzo.paste(im, (x0, y0))
        guia_modelo(d, x0, y0, im.width, im.height)
    if miniatura is not None:
        lienzo.paste(miniatura, (20, 20))
        d.rectangle([20, 20, 20 + miniatura.width, 20 + miniatura.height], outline=TEXTO, width=3)
        etiqueta(d, (30, 30 + miniatura.height), "última captura", 20)
    y = 30 if miniatura is None else 80 + miniatura.height
    if info:
        etiqueta(d, (30, y), info)
        y += 50
    if alerta:
        etiqueta(d, (30, y), alerta, 22, NARANJA)
    etiqueta(d, (30, VID_H - 52), ayuda)
    lienzo.paste(panel, (VID_W, 0))
    lienzo.paste(pie, (0, VID_H))
    return cv2.cvtColor(np.asarray(lienzo), cv2.COLOR_RGB2BGR)


def miniatura_de(rgb, ancho_px=240):
    h, w = rgb.shape[:2]
    return Image.fromarray(cv2.resize(rgb, (ancho_px, max(1, int(h * ancho_px / w))),
                                      interpolation=cv2.INTER_AREA))


# --------------------------------------------------------------------------
# Ventana

VENTANA = "SERB - Flora de Jalisco"


def abrir_ventana(completa):
    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(VENTANA, W, H)
    if completa:
        alternar_completa()


def alternar_completa():
    actual = cv2.getWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN,
                          cv2.WINDOW_NORMAL if actual == cv2.WINDOW_FULLSCREEN
                          else cv2.WINDOW_FULLSCREEN)


def ventana_cerrada():
    try:
        return cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1
    except cv2.error:
        return True


# --------------------------------------------------------------------------
# Fuentes de imagen

class Camara:
    """Camara (o video) que puede no existir: abrir() nunca lanza."""

    def __init__(self, origen, ancho_px, alto_px):
        self.origen = int(origen) if str(origen).isdigit() else origen
        self.ancho_px, self.alto_px = ancho_px, alto_px
        self.cap = None

    @property
    def abierta(self):
        return self.cap is not None

    def abrir(self):
        if self.abierta:
            return True
        try:
            cap = cv2.VideoCapture(self.origen)
            if not cap.isOpened():
                cap.release()
                return False
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.ancho_px)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.alto_px)
        except cv2.error:
            return False
        self.cap = cap
        return True

    def leer(self):
        """Frame RGB, o None si la camara no entrega."""
        if not self.abierta:
            return None
        ok, frame = self.cap.read()
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ok and frame is not None else None

    def vaciar_buffer(self, n=4):
        """Descarta frames viejos acumulados mientras se estuvo en galeria."""
        for _ in range(n):
            self.cap.grab()

    def cerrar(self):
        if self.abierta:
            self.cap.release()
            self.cap = None


class Galeria:
    """Imagenes de una carpeta, clasificadas por la ruta de archivo (la
    calibrada) la primera vez que se muestran."""

    def __init__(self, carpeta, pred):
        self.carpeta, self.pred = Path(carpeta), pred
        self.rutas = (sorted(p for p in self.carpeta.rglob("*") if p.suffix.lower() in EXTS)
                      if self.carpeta.is_dir() else [])
        self.i = 0
        self._cache = {}

    def mover(self, paso):
        if self.rutas:
            self.i = (self.i + paso) % len(self.rutas)

    def vista(self):
        """(rgb | None, panel, info) de la imagen actual."""
        if not self.rutas:
            return None, dibujar_panel({
                "tipo": "espera", "rotulo": "GALERÍA VACÍA",
                "mensaje": f"No hay imágenes en la carpeta «{self.carpeta.name}». "
                           "Inicie con --carpeta RUTA."}), \
                "GALERÍA  0/0"
        ruta = self.rutas[self.i]
        if self.i not in self._cache:
            try:
                rgb = np.asarray(Image.open(ruta).convert("RGB"))
                r = self.pred.predecir(ruta)
                self._cache[self.i] = (rgb, dibujar_panel({"tipo": "resultado", "resultado": r}))
                print(f"[{ruta}] {r['identificacion']} conf={r['confianza']:.3f} riesgo={r['riesgo']}")
            except (OSError, ValueError) as e:
                print(f"[{ruta}] ERROR: {e}", file=sys.stderr)
                self._cache[self.i] = (None, dibujar_panel(
                    {"tipo": "error", "mensaje": f"{ruta.name}: {e}"}))
        rgb, panel = self._cache[self.i]
        return rgb, panel, f"GALERÍA  {self.i + 1}/{len(self.rutas)}  {ruta.relative_to(self.carpeta)}"


# --------------------------------------------------------------------------
# Sesion: camara y galeria en el mismo bucle

AYUDA_CAM = "ESPACIO capturar    G galería    F pantalla completa    ESC salir"
AYUDA_GAL = "←  →  navegar    C cámara    F pantalla completa    ESC salir"
SIN_CAMARA = "Cámara no disponible · modo galería (C para reintentar)"
PANEL_ESPERA = {"tipo": "espera",
                "mensaje": "Encuadre la planta dentro del recuadro y pulse ESPACIO."}


def capturar(pred, cam, primero, n):
    """n frames seguidos sin recomprimir -> (resultado, frames) o (None, frames)
    si la camara no entrego los n."""
    frames = [primero]
    while len(frames) < n:
        f = cam.leer()
        if f is None:
            return None, frames
        frames.append(f)
    t0 = time.perf_counter()
    r = pred.predecir_promedio([Image.fromarray(x) for x in frames],
                               nombre=time.strftime("captura %H:%M:%S"))
    print(f"[{r['imagen']}] {r['identificacion']} conf={r['confianza']:.3f} "
          f"por_frame={r['confianza_por_imagen']} riesgo={r['riesgo']} "
          f"({time.perf_counter() - t0:.2f}s)")
    return r, frames


def sesion(pred, a):
    cam = Camara(a.camara, a.ancho, a.alto)
    gal = Galeria(a.carpeta, pred)
    pie = dibujar_pie()
    panel_cam, mini = dibujar_panel(PANEL_ESPERA), None   # la ultima captura sobrevive al cambio de modo

    alerta = None                 # texto naranja sobre la imagen (estado de la camara)
    if cam.abrir():
        modo = "camara"
    else:
        modo, alerta = "galeria", SIN_CAMARA
        print(f"No se pudo abrir la camara {a.camara!r}: se arranca en galeria ({gal.carpeta}). "
              "(En WSL la webcam no es visible sin usbipd.)", file=sys.stderr)
    redibujar = True              # la galeria solo se repinta cuando cambia algo
    abrir_ventana(a.pantalla_completa)

    while True:
        if modo == "camara":
            rgb = cam.leer()
            if rgb is None:
                print("La camara dejo de entregar frames: se pasa a galeria.", file=sys.stderr)
                cam.cerrar()
                modo, redibujar = "galeria", True
                alerta = "La cámara dejó de entregar frames · modo galería (C para reintentar)"
                continue
            cv2.imshow(VENTANA, componer(rgb, panel_cam, pie, AYUDA_CAM, info="CÁMARA", miniatura=mini))
            k = cv2.waitKeyEx(1)
        else:
            if redibujar:
                g_rgb, g_panel, g_info = gal.vista()
                cv2.imshow(VENTANA, componer(g_rgb, g_panel, pie, AYUDA_GAL, info=g_info, alerta=alerta))
                redibujar = False
            k = cv2.waitKeyEx(50)

        if k in TECLAS_SALIR or ventana_cerrada():
            break
        if k in TECLAS_COMPLETA:
            alternar_completa()
        elif k in TECLAS_GALERIA and modo == "camara":
            modo, redibujar = "galeria", True
        elif k in TECLAS_CAMARA and modo == "galeria":
            if cam.abierta:
                cam.vaciar_buffer()
                modo, alerta = "camara", None
            elif cam.abrir():
                modo, alerta = "camara", None
            else:
                alerta, redibujar = SIN_CAMARA, True
        elif modo == "galeria" and k in TECLAS_DER:
            gal.mover(1)
            redibujar = True
        elif modo == "galeria" and k in TECLAS_IZQ:
            gal.mover(-1)
            redibujar = True
        elif modo == "camara" and k == ESPACIO:
            cv2.imshow(VENTANA, componer(rgb, dibujar_panel(
                {"tipo": "analizando",
                 "mensaje": f"Tomando {a.frames} frames. Mantenga la cámara quieta."}),
                pie, AYUDA_CAM, info="CÁMARA", miniatura=mini))
            cv2.waitKey(1)
            r, frames = capturar(pred, cam, rgb, a.frames)
            if r is None:
                panel_cam = dibujar_panel({"tipo": "error", "mensaje":
                                           f"Solo se obtuvieron {len(frames)} de {a.frames} frames."})
            else:
                panel_cam = dibujar_panel({"tipo": "resultado", "resultado": r})
                mini = miniatura_de(frames[len(frames) // 2])

    cam.cerrar()
    cv2.destroyAllWindows()
    return 0


def main():
    ap = argparse.ArgumentParser(description="Demo en vivo del clasificador SERB v1.")
    ap.add_argument("--carpeta", default=str(GALERIA_DEFECTO),
                    help="carpeta de imagenes del modo galeria (default demo/galeria)")
    ap.add_argument("--camara", default="0", help="indice de camara o ruta a video (default 0)")
    ap.add_argument("--frames", type=int, default=5,
                    help="frames seguidos promediados por captura (default 5)")
    ap.add_argument("--ancho", type=int, default=1280, help="resolucion solicitada a la camara")
    ap.add_argument("--alto", type=int, default=720)
    ap.add_argument("--umbral", type=float, default=UMBRAL, help=f"default {UMBRAL}")
    ap.add_argument("--corte-riesgo", type=float, default=CORTE_RIESGO, help=f"default {CORTE_RIESGO}")
    ap.add_argument("--pantalla-completa", action="store_true")
    ap.add_argument("--cpu", action="store_true", help="forzar CPU aunque haya GPU")
    a = ap.parse_args()
    if a.frames < 1:
        ap.error("--frames debe ser >= 1")

    print("Cargando modelo...", flush=True)
    pred = Predictor(umbral=a.umbral, corte_riesgo=a.corte_riesgo, device="cpu" if a.cpu else None)
    return sesion(pred, a)


if __name__ == "__main__":
    sys.exit(main())
