# =====================================================================
#  FONDO "GEOFRONT" TOON (v2)  —  colores y estilo de toon_atardecer.py
#  para EVANGELION.blend  —  Blender 5.1+ (EEVEE)
#
#  Lago en el centro, montañas, pirámide luminosa y una ciudad colgando
#  boca abajo del techo, pintado con el MISMO estilo cartoon que el EVA:
#    • Bandas de luz duras (sombra / medio / luz) con los mismos umbrales
#      (0.10 y 0.30), sombra teñida de morado (#b4a5cf) y luz de borde
#      naranja (#ffa04d), igual que el grupo "Toon Cartoon".
#    • Cielo de atardecer con el mismo degradado y el sol pintado de
#      toon_atardecer.py (amarillo -> naranja -> rosa -> morado).
#    • Bruma "por capas": los planos lejanos se aclaran por escalones
#      (como en los fondos de anime), sin degradados.
#    • Agua con reflejos posterizados (también por bandas).
#
#  Cómo usarlo:
#    1. Abre EVANGELION.blend.  Scripting > Abrir > este archivo > ▶ Ejecutar.
#    2. Todo queda en la colección "Geofront Toon", colgado del vacío
#       "GT Raiz": muévelo / gíralo / escálalo para recolocar el fondo.
#    3. Volver a ejecutarlo regenera solo el fondo.  Si existía el fondo de la
#       v1 ("Geofront Fondo") lo oculta, no lo borra.
#
#  Rendimiento:
#    • Sin luces nuevas ni sombras: el sombreado toon del fondo se calcula en
#      el shader con una luz "falsa" en la misma dirección que el sol del
#      EVA (LUZ_AZIMUT / LUZ_ELEVACION de toon_atardecer.py).
#    • Terreno low-poly facetado (malla radial: más detalle cerca, menos lejos).
#    • Árboles, edificios y luces son instancias (Geometry Nodes).
#    • Shaders cortos: sin ruidos de detalle, solo colores planos por bandas.
#    • Compositor mínimo: solo Bloom (el mismo de material_bloom.py).
# =====================================================================

import bpy
import bmesh
import math
import random
from mathutils import Vector, noise

# ---------------------------- AJUSTES --------------------------------
SEMILLA = 11
NIVEL_AGUA = 0.45             # altura del agua sobre los pies del modelo
TAMANO_MUNDO = 1.0

# Igual que toon_atardecer.py
TINTE_SOMBRA = "#b4a5cf"      # multiplica el color en la sombra
UMBRAL_MEDIO = 0.10
UMBRAL_LUZ = 0.30
COLOR_BORDE = "#ffa04d"
FUERZA_BORDE = 0.6
LUZ_AZIMUT = 35.0             # 0 = de frente, + = desde la izquierda
LUZ_ELEVACION = 22.0
SOL_CIELO_AZIMUT = 14.0       # sol pintado en el cielo, detrás
SOL_CIELO_ELEVACION = 4.0
LUZ_AMBIENTE = 0.15

# Contenido (más bajo = más rápido)
ALTURA_TECHO = 900.0
NUM_EDIFICIOS = 550
LARGO_MAX_EDIFICIO = 470.0
VENTANAS_ENCENDIDAS = 0.18
NUM_ARBOLES = 9000
DISTANCIA_ARBOLES = 2200.0
PIRAMIDE_BASE = 250.0
PIRAMIDE_ALTO = 175.0
FUERZA_PIRAMIDE = 3.0
NUM_RAYOS = 8
NUM_LUCES_TECHO = 40
CAPAS_BRUMA = 1.0             # 0 = sin bruma; 2 = las capas empiezan más cerca

CREAR_CAMARA = True
USAR_MUNDO = True
USAR_COMPOSITOR = True
REFLEJOS_AGUA = True          # False = agua plana (aún más rápido)
AJUSTES_RENDER = True
# ---------------------------------------------------------------------

PALETA = dict(
    # bruma por altura (como el cielo cerca del horizonte -> arriba)
    bruma_baja="#ff9f45", bruma_alta="#d44a7a",
    bosque="#4d5a3a", bosque2="#6b6436", roca="#9a6a5e", roca2="#6e4658",
    nieve="#ffe8cc", arena="#ffcf9a",
    agua="#3a1a40", agua_claro="#ff9f6a",
    arbol="#3f5236", arbol2="#5e6a34",
    edificio=["#f0c8a0", "#e8b49a", "#c99a9a", "#a07a96", "#d9a48a"],
    ventana_off="#5a3a6a", ventana_on="#ffe4a8",
    piramide="#fff4d6", piramide_marco="#7a3488",
    nube="#c45a7a", nube_sombra="#8e3f80", nube_filo="#ffe4a8",
    rayo="#ffc879", luz_techo="#fff4d6", techo="#33236a",
)

COL = "Geofront Toon"
COL_V1 = "Geofront Fondo"
COL_FUENTES = "GT Fuentes (no tocar)"
RAIZ = "GT Raiz"
CAM = "Camara Geofront"
MUNDO = "GT Cielo Atardecer"
COMPOSITOR = "Compositor Geofront Toon"
GRUPO_TOON = "GT Toon Fondo"
PREFIJO = "GT "

LAGO = dict(cx=60.0, cy=950.0, rx_izq=300.0, rx_der=820.0, ry=1180.0)
ISLA = dict(x=-40.0, y=1500.0, r=230.0, alto=16.0)
PICOS = [
    (-950.0, 1450.0, 880.0, 520.0),
    (-1500.0, 2300.0, 900.0, 650.0),
    (1450.0, 2700.0, 620.0, 520.0),
    (300.0, 3900.0, 720.0, 900.0),
    (2300.0, 1500.0, 520.0, 500.0),
]
CIUDAD = dict(cx=0.0, cy=2050.0, rx=1700.0, ry=1350.0)
POS_CAMARA = Vector((0.0, -34.0, 4.5))
MIRA_CAMARA = Vector((0.0, 260.0, 66.0))


# =====================================================================
#  Utilidades
# =====================================================================
def lin(hexstr, a=1.0):
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (a,)


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def nd(nodes, idname, x, y, label=None, **props):
    n = nodes.new(idname)
    n.location = (x, y)
    if label:
        n.label = label
    for k, v in props.items():
        setattr(n, k, v)
    return n


def vmath(N, L, x, y, op, a, b=None, label=None):
    n = nd(N, "ShaderNodeVectorMath", x, y, label, operation=op)
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, bpy.types.NodeSocket):
            L.new(v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    return n.outputs["Value"] if op in {"DOT_PRODUCT", "LENGTH", "DISTANCE"} else n.outputs["Vector"]


def math_(N, L, x, y, op, a, b=0.0, label=None, clamp=False):
    n = nd(N, "ShaderNodeMath", x, y, label, operation=op, use_clamp=clamp)
    for i, v in enumerate((a, b)):
        if isinstance(v, bpy.types.NodeSocket):
            L.new(v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    return n.outputs[0]


def mapr(N, L, x, y, val, fmin, fmax, tmin=0.0, tmax=1.0, label=None, interp="LINEAR"):
    n = nd(N, "ShaderNodeMapRange", x, y, label, interpolation_type=interp, clamp=True)
    L.new(val, n.inputs["Value"])
    for name, v in (("From Min", fmin), ("From Max", fmax), ("To Min", tmin), ("To Max", tmax)):
        if isinstance(v, bpy.types.NodeSocket):
            L.new(v, n.inputs[name])
        else:
            n.inputs[name].default_value = v
    return n.outputs["Result"]


def mixc(N, L, x, y, fac, a, b, blend="MIX", label=None):
    n = nd(N, "ShaderNodeMix", x, y, label, data_type="RGBA", blend_type=blend)
    n.clamp_result = True
    for idx, v in ((0, fac), (6, a), (7, b)):
        if isinstance(v, bpy.types.NodeSocket):
            L.new(v, n.inputs[idx])
        else:
            n.inputs[idx].default_value = v
    return n.outputs[2]


def ramp(N, x, y, stops, interp="LINEAR", label=None):
    r = nd(N, "ShaderNodeValToRGB", x, y, label)
    cr = r.color_ramp
    cr.interpolation = interp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = lin(stops[0][1])
    for pos, col in stops[1:]:
        e = cr.elements.new(pos)
        e.color = lin(col)
    return r


def ruido(N, L, x, y, vec, escala, detalle=3.0, rug=0.55, dim="3D"):
    n = nd(N, "ShaderNodeTexNoise", x, y, noise_dimensions=dim)
    if vec is not None:
        L.new(vec, n.inputs["Vector"])
    n.inputs["Scale"].default_value = escala
    n.inputs["Detail"].default_value = detalle
    n.inputs["Roughness"].default_value = rug
    return n


def nuevo_material(nombre):
    m = bpy.data.materials.get(nombre) or bpy.data.materials.new(nombre)
    if m.node_tree is None:
        m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, m.node_tree.nodes, m.node_tree.links


def salida(N, L, shader, x=1400, y=0):
    out = nd(N, "ShaderNodeOutputMaterial", x, y)
    L.new(shader, out.inputs["Surface"])
    return out



def opcion(node, nombre, valores):
    s = node.inputs.get(nombre)
    if s is None:
        return False
    for v in (valores if isinstance(valores, (list, tuple)) else [valores]):
        try:
            s.default_value = v
            return True
        except Exception:
            continue
    return False




def dir_luz():
    """Misma dirección que el sol de toon_atardecer.py (hacia la luz)."""
    az, el = math.radians(LUZ_AZIMUT), math.radians(LUZ_ELEVACION)
    return Vector((-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))


def dir_sol():
    """Sol pintado en el cielo (detrás del fondo)."""
    az, el = math.radians(SOL_CIELO_AZIMUT), math.radians(SOL_CIELO_ELEVACION)
    return Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))


def lin_socket(N, L, x, y, val):
    if isinstance(val, bpy.types.NodeSocket):
        return val
    r = nd(N, "ShaderNodeRGB", x, y)
    r.outputs[0].default_value = val
    return r.outputs[0]


# =====================================================================
#  1. Grupo toon del fondo (bandas + sombra morada + borde naranja + bruma)
# =====================================================================
def grupo_toon():
    ng = bpy.data.node_groups.get(GRUPO_TOON)
    if ng:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(GRUPO_TOON, "ShaderNodeTree")
    it = ng.interface

    def ent(nombre, tipo, val):
        s = it.new_socket(nombre, in_out="INPUT", socket_type=tipo)
        s.default_value = val
    ent("Color", "NodeSocketColor", (0.8, 0.8, 0.8, 1))
    ent("Sombreado", "NodeSocketFloat", 1.0)
    ent("Bruma", "NodeSocketFloat", 1.0)
    ent("Tinte sombra", "NodeSocketColor", lin(TINTE_SOMBRA))
    ent("Fuerza borde", "NodeSocketFloat", FUERZA_BORDE)
    it.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    it.new_socket("Factor bruma", in_out="OUTPUT", socket_type="NodeSocketFloat")
    N, L = ng.nodes, ng.links
    gi = nd(N, "NodeGroupInput", -1100, 0)
    go = nd(N, "NodeGroupOutput", 900, 0)
    c_in = gi.outputs["Color"]

    # bandas de luz (mismos umbrales que "Toon Cartoon")
    geo = nd(N, "ShaderNodeNewGeometry", -1100, 400)
    d = vmath(N, L, -900, 400, "DOT_PRODUCT", geo.outputs["Normal"], tuple(dir_luz()))
    d = math_(N, L, -720, 400, "MAXIMUM", d, 0.0)
    b = ramp(N, -560, 400, [(0.0, "#000000"), (UMBRAL_MEDIO, "#808080"), (UMBRAL_LUZ, "#ffffff")],
             "CONSTANT", "Bandas de luz (ajusta aquí)")
    # (la rampa usa colores sRGB: #808080 -> 0.216 lineal; se corrige con BW+potencia)
    b.color_ramp.elements[1].color = (0.5, 0.5, 0.5, 1)
    L.new(d, b.inputs["Fac"])
    bw = nd(N, "ShaderNodeRGBToBW", -300, 400)
    L.new(b.outputs["Color"], bw.inputs["Color"])
    sinluz = math_(N, L, -150, 400, "SUBTRACT", 1.0, bw.outputs["Val"])
    luz = math_(N, L, 0, 400, "SUBTRACT", 1.0,
                math_(N, L, -60, 300, "MULTIPLY", sinluz, gi.outputs["Sombreado"]), clamp=True)

    sombra = mixc(N, L, -300, 100, 1.0, c_in, gi.outputs["Tinte sombra"], blend="MULTIPLY",
                  label="Color en sombra")
    base = mixc(N, L, 150, 100, luz, sombra, c_in, label="Sombra / luz")

    # luz de borde naranja, solo en la parte iluminada
    lw = nd(N, "ShaderNodeLayerWeight", -600, -200)
    lw.inputs["Blend"].default_value = 0.5
    borde = math_(N, L, -400, -200, "GREATER_THAN", lw.outputs["Facing"], 0.7)
    borde = math_(N, L, -250, -200, "MULTIPLY", borde, gi.outputs["Fuerza borde"])
    borde = math_(N, L, -100, -200, "MULTIPLY", borde, luz)
    col = mixc(N, L, 350, 50, borde, base, lin(COLOR_BORDE), blend="SCREEN", label="Luz de borde")

    # bruma por capas (escalones según la distancia) y color según la altura
    cam = nd(N, "ShaderNodeCameraData", -900, -500)
    dist = math_(N, L, -700, -500, "MULTIPLY", cam.outputs["View Distance"],
                 CAPAS_BRUMA / (7000.0 * TAMANO_MUNDO))
    dist = math_(N, L, -550, -500, "MULTIPLY", dist, gi.outputs["Bruma"])
    capas = ramp(N, -400, -500, [(0.0, "#000000"), (0.09, "#2e2e2e"), (0.22, "#5c5c5c"),
                                 (0.42, "#8a8a8a"), (0.75, "#b8b8b8")], "CONSTANT", "Capas de bruma")
    for e, v in zip(capas.color_ramp.elements, (0.0, 0.18, 0.36, 0.55, 0.74)):
        e.color = (v, v, v, 1)
    L.new(dist, capas.inputs["Fac"])
    fbw = nd(N, "ShaderNodeRGBToBW", -150, -500)
    L.new(capas.outputs["Color"], fbw.inputs["Color"])
    sep = nd(N, "ShaderNodeSeparateXYZ", -900, -750)
    L.new(geo.outputs["Position"], sep.inputs[0])
    h = mapr(N, L, -700, -750, sep.outputs["Z"], 0.0, ALTURA_TECHO * TAMANO_MUNDO)
    fcol = mixc(N, L, -400, -750, h, lin(PALETA["bruma_baja"]), lin(PALETA["bruma_alta"]))
    col = mixc(N, L, 550, 0, fbw.outputs["Val"], col, fcol, label="Bruma")

    e = nd(N, "ShaderNodeEmission", 720, 0)
    L.new(col, e.inputs["Color"])
    L.new(e.outputs[0], go.inputs["Shader"])
    L.new(fbw.outputs["Val"], go.inputs["Factor bruma"])
    return ng


def toon(N, L, ng, x, y, color, sombreado=1.0, bruma=1.0):
    g = nd(N, "ShaderNodeGroup", x, y, "Toon")
    g.node_tree = ng
    if isinstance(color, bpy.types.NodeSocket):
        L.new(color, g.inputs["Color"])
    else:
        g.inputs["Color"].default_value = color
    g.inputs["Sombreado"].default_value = sombreado
    g.inputs["Bruma"].default_value = bruma
    return g


# =====================================================================
#  2. Materiales (colores planos)
# =====================================================================
def mat_terreno(ng):
    m, N, L = nuevo_material(PREFIJO + "Terreno")
    tc = nd(N, "ShaderNodeTexCoord", -1200, 0)
    sep = nd(N, "ShaderNodeSeparateXYZ", -1000, 100)
    L.new(tc.outputs["Object"], sep.inputs[0])
    rn = ruido(N, L, -1000, -150, tc.outputs["Object"], 0.006 / TAMANO_MUNDO, 2.0, 0.5)
    # altura con un poco de ruido para que las bandas no sean rectas
    z = math_(N, L, -800, 100, "ADD", sep.outputs["Z"],
              math_(N, L, -850, -50, "MULTIPLY", rn.outputs["Fac"], 160.0 * TAMANO_MUNDO))
    zf = mapr(N, L, -650, 100, z, 0.0, 1000.0 * TAMANO_MUNDO)
    r = ramp(N, -450, 100, [(0.0, PALETA["arena"]), (0.083, PALETA["bosque"]),
                            (0.30, PALETA["roca"]), (0.66, PALETA["nieve"])], "CONSTANT",
             "Arena / bosque / roca / nieve")
    L.new(zf, r.inputs["Fac"])
    # pendiente fuerte = roca oscura; manchas de bosque más claro
    geo = nd(N, "ShaderNodeNewGeometry", -1000, -400)
    sn = nd(N, "ShaderNodeSeparateXYZ", -800, -400)
    L.new(geo.outputs["Normal"], sn.inputs[0])
    empinado = math_(N, L, -600, -400, "LESS_THAN", sn.outputs["Z"], 0.62)
    empinado = math_(N, L, -450, -400, "MULTIPLY", empinado,
                     math_(N, L, -600, -300, "LESS_THAN", zf, 0.6))
    c = mixc(N, L, -200, 100, empinado, r.outputs["Color"], lin(PALETA["roca2"]))
    mancha = math_(N, L, -450, -150, "MULTIPLY",
                   math_(N, L, -600, -150, "GREATER_THAN", rn.outputs["Fac"], 0.55),
                   math_(N, L, -600, -230, "LESS_THAN", zf, 0.25))
    c = mixc(N, L, 0, 100, mancha, c, lin(PALETA["bosque2"]))
    salida(N, L, toon(N, L, ng, 250, 100, c).outputs["Shader"], 500, 100)
    return m


def mat_arbol(ng):
    m, N, L = nuevo_material(PREFIJO + "Arbol")
    oi = nd(N, "ShaderNodeObjectInfo", -600, 0)
    c = mixc(N, L, -350, 0, math_(N, L, -450, -100, "GREATER_THAN", oi.outputs["Random"], 0.6),
             lin(PALETA["arbol"]), lin(PALETA["arbol2"]))
    salida(N, L, toon(N, L, ng, -100, 0, c).outputs["Shader"], 150, 0)
    return m


def mat_edificio(ng):
    m, N, L = nuevo_material(PREFIJO + "Edificio")
    geo = nd(N, "ShaderNodeNewGeometry", -1500, 0)
    oi = nd(N, "ShaderNodeObjectInfo", -1500, 400)
    sep = nd(N, "ShaderNodeSeparateXYZ", -1300, 0)
    L.new(geo.outputs["Position"], sep.inputs[0])
    u = math_(N, L, -1150, 50, "DIVIDE",
              math_(N, L, -1250, 100, "ADD", sep.outputs["X"], sep.outputs["Y"]), 8.0 * TAMANO_MUNDO)
    v = math_(N, L, -1150, -100, "DIVIDE", sep.outputs["Z"], 7.0 * TAMANO_MUNDO)
    mu = math_(N, L, -900, 50, "LESS_THAN", math_(N, L, -1000, 50, "FRACT", u), 0.6)
    mv = math_(N, L, -900, -100, "LESS_THAN", math_(N, L, -1000, -100, "FRACT", v), 0.5)
    ventana = math_(N, L, -750, 0, "MULTIPLY", mu, mv)
    comb = nd(N, "ShaderNodeCombineXYZ", -900, -300)
    L.new(math_(N, L, -1000, -250, "FLOOR", u), comb.inputs["X"])
    L.new(math_(N, L, -1000, -350, "FLOOR", v), comb.inputs["Y"])
    L.new(math_(N, L, -1000, -450, "MULTIPLY", oi.outputs["Random"], 97.0), comb.inputs["Z"])
    wn = nd(N, "ShaderNodeTexWhiteNoise", -750, -300, noise_dimensions="3D")
    L.new(comb.outputs["Vector"], wn.inputs["Vector"])
    on = math_(N, L, -600, -300, "MULTIPLY", ventana,
               math_(N, L, -650, -400, "GREATER_THAN", wn.outputs["Value"], 1.0 - VENTANAS_ENCENDIDAS))

    pal = PALETA["edificio"]
    r = ramp(N, -1100, 400, [(i / len(pal), h) for i, h in enumerate(pal)], "CONSTANT")
    L.new(oi.outputs["Random"], r.inputs["Fac"])
    c = mixc(N, L, -400, 200, math_(N, L, -500, 100, "MULTIPLY", ventana, 0.5),
             r.outputs["Color"], lin(PALETA["ventana_off"]))
    g = toon(N, L, ng, -150, 200, c)
    # ventanas encendidas: planas, sin sombreado, y ocultas por la bruma
    vis = math_(N, L, -150, -150, "SUBTRACT", 1.0, g.outputs["Factor bruma"])
    fz = math_(N, L, 0, -150, "MULTIPLY", math_(N, L, -50, -250, "MULTIPLY", on, vis), 1.6)
    e = nd(N, "ShaderNodeEmission", 150, -100)
    e.inputs["Color"].default_value = lin(PALETA["ventana_on"])
    L.new(fz, e.inputs["Strength"])
    add = nd(N, "ShaderNodeAddShader", 350, 100)
    L.new(g.outputs["Shader"], add.inputs[0])
    L.new(e.outputs[0], add.inputs[1])
    salida(N, L, add.outputs[0], 550, 100)
    return m


def mat_piramide(ng):
    m, N, L = nuevo_material(PREFIJO + "Piramide")
    tc = nd(N, "ShaderNodeTexCoord", -1200, 0)
    sep = nd(N, "ShaderNodeSeparateXYZ", -1000, 0)
    L.new(tc.outputs["Object"], sep.inputs[0])
    x, y, z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    def linea(val, yy, n=10.0, ancho=0.12):
        f = math_(N, L, -650, yy, "FRACT", math_(N, L, -750, yy, "MULTIPLY", val, n))
        return math_(N, L, -500, yy, "LESS_THAN", f, ancho)
    l1 = linea(math_(N, L, -850, 200, "ADD", math_(N, L, -950, 250, "ADD", x, y), z), 200)
    l2 = linea(math_(N, L, -850, 0, "ADD", math_(N, L, -950, 50, "SUBTRACT", x, y), z), 0)
    l3 = linea(z, -200, 6.0, 0.15)
    marco = math_(N, L, -300, 0, "MAXIMUM", math_(N, L, -350, 100, "MAXIMUM", l1, l2), l3)
    # brillo por bandas: más fuerte abajo
    alto = ramp(N, -650, 450, [(0.0, "#ffffff"), (0.35, "#bfbfbf"), (0.7, "#8c8c8c")], "CONSTANT")
    for e_, v_ in zip(alto.color_ramp.elements, (1.0, 0.75, 0.55)):
        e_.color = (v_, v_, v_, 1)
    L.new(z, alto.inputs["Fac"])
    abw = nd(N, "ShaderNodeRGBToBW", -400, 450)
    L.new(alto.outputs["Color"], abw.inputs["Color"])
    e = nd(N, "ShaderNodeEmission", -100, 350)
    e.inputs["Color"].default_value = lin(PALETA["piramide"])
    L.new(math_(N, L, -250, 450, "MULTIPLY", abw.outputs["Val"], FUERZA_PIRAMIDE), e.inputs["Strength"])
    g = toon(N, L, ng, -100, -200, lin(PALETA["piramide_marco"]), 0.0, 0.8)
    mix = nd(N, "ShaderNodeMixShader", 200, 100)
    L.new(marco, mix.inputs[0])
    L.new(e.outputs[0], mix.inputs[1])
    L.new(g.outputs["Shader"], mix.inputs[2])
    salida(N, L, mix.outputs[0], 400, 100)
    return m


def mat_agua(ng):
    m, N, L = nuevo_material(PREFIJO + "Agua")
    tc = nd(N, "ShaderNodeTexCoord", -1200, 0)
    mp = nd(N, "ShaderNodeMapping", -1000, 0)
    mp.inputs["Scale"].default_value = (0.25, 6.0, 1.0)       # rayas horizontales
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    rn = ruido(N, L, -800, 0, mp.outputs["Vector"], 0.08 / TAMANO_MUNDO, 1.0, 0.5)
    rayas = math_(N, L, -600, 0, "GREATER_THAN", rn.outputs["Fac"], 0.68)
    c = mixc(N, L, -350, 100, math_(N, L, -450, -100, "MULTIPLY", rayas, 0.55),
             lin(PALETA["agua"]), lin(PALETA["agua_claro"]), label="Brillos del agua")
    g = toon(N, L, ng, -100, 100, c, 0.0, 0.35)
    if not REFLEJOS_AGUA:
        salida(N, L, g.outputs["Shader"], 400, 100)
        return m
    # reflejo tipo espejo (EVA, montañas, pirámide) mezclado con el color plano;
    # las rayas cortan el reflejo como en los fondos dibujados
    gl = nd(N, "ShaderNodeBsdfGlossy", -100, -150)
    gl.inputs["Roughness"].default_value = 0.0
    gl.inputs["Color"].default_value = lin("#ffd6c0")
    f = math_(N, L, -100, -350, "MULTIPLY", math_(N, L, -250, -350, "SUBTRACT", 1.0, rayas),
              math_(N, L, -250, -450, "SUBTRACT", 1.0, g.outputs["Factor bruma"]))
    f = math_(N, L, 50, -350, "MULTIPLY", f, 0.85)
    mix = nd(N, "ShaderNodeMixShader", 200, 50)
    L.new(f, mix.inputs[0])
    L.new(g.outputs["Shader"], mix.inputs[1])
    L.new(gl.outputs[0], mix.inputs[2])
    salida(N, L, mix.outputs[0], 400, 50)
    return m


def mat_rayo():
    m, N, L = nuevo_material(PREFIJO + "Rayo de luz")
    m.surface_render_method = "BLENDED"
    uv = nd(N, "ShaderNodeUVMap", -900, 0)
    sep = nd(N, "ShaderNodeSeparateXYZ", -700, 0)
    L.new(uv.outputs["UV"], sep.inputs[0])
    s = math_(N, L, -550, 100, "SINE", math_(N, L, -650, 100, "MULTIPLY", sep.outputs["X"], math.pi))
    nucleo = math_(N, L, -400, 100, "ADD", math_(N, L, -450, 150, "GREATER_THAN", s, 0.35),
                   math_(N, L, -450, 50, "GREATER_THAN", s, 0.85))          # 2 tonos
    largo = ramp(N, -550, -150, [(0.0, "#000000"), (0.25, "#808080"), (0.55, "#ffffff")], "CONSTANT")
    largo.color_ramp.elements[1].color = (0.5, 0.5, 0.5, 1)
    L.new(sep.outputs["Y"], largo.inputs["Fac"])
    lbw = nd(N, "ShaderNodeRGBToBW", -300, -150)
    L.new(largo.outputs["Color"], lbw.inputs["Color"])
    a = math_(N, L, -200, 50, "MULTIPLY", nucleo, lbw.outputs["Val"])
    a = math_(N, L, -50, 50, "MULTIPLY", a, 0.16)
    e = nd(N, "ShaderNodeEmission", 100, 150)
    e.inputs["Color"].default_value = lin(PALETA["rayo"])
    L.new(a, e.inputs["Strength"])
    t = nd(N, "ShaderNodeBsdfTransparent", 100, -50)
    add = nd(N, "ShaderNodeAddShader", 300, 50)
    L.new(t.outputs[0], add.inputs[0])
    L.new(e.outputs[0], add.inputs[1])
    salida(N, L, add.outputs[0], 500, 50)
    return m


def mat_nube(ng):
    m, N, L = nuevo_material(PREFIJO + "Nube techo")
    m.surface_render_method = "DITHERED"        # borde duro: más barato que transparente suave
    tc = nd(N, "ShaderNodeTexCoord", -1100, 0)
    oi = nd(N, "ShaderNodeObjectInfo", -1100, -300)
    mp = nd(N, "ShaderNodeMapping", -900, 0)
    mp.inputs["Scale"].default_value = (CIUDAD["rx"] * 1.25 / 1000.0, CIUDAD["ry"] * 1.3 / 1000.0, 1.0)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    L.new(math_(N, L, -1000, -300, "MULTIPLY", oi.outputs["Random"], 31.0), mp.inputs["Location"])
    n1 = ruido(N, L, -700, 100, mp.outputs["Vector"], 2.0, 2.0, 0.5)
    mp2 = nd(N, "ShaderNodeMapping", -900, -200)
    mp2.inputs["Location"].default_value = (0.0, -0.06, 0.0)
    L.new(mp.outputs["Vector"], mp2.inputs["Vector"])
    n2 = ruido(N, L, -700, -200, mp2.outputs["Vector"], 2.0, 2.0, 0.5)
    rad = vmath(N, L, -700, -450, "LENGTH", tc.outputs["Object"])
    umbral = mapr(N, L, -500, -450, rad, 0.5, 1.0, 0.50, 0.75)       # más ralas en el borde
    c1 = math_(N, L, -350, 100, "GREATER_THAN", n1.outputs["Fac"], umbral)
    c2 = math_(N, L, -350, -100, "GREATER_THAN", n2.outputs["Fac"], umbral)
    filo = math_(N, L, -200, 0, "SUBTRACT", c1, c2, clamp=True)
    col = mixc(N, L, -200, 300, math_(N, L, -350, 250, "GREATER_THAN", n1.outputs["Fac"], 0.62),
               lin(PALETA["nube_sombra"]), lin(PALETA["nube"]))
    col = mixc(N, L, 0, 300, filo, col, lin(PALETA["nube_filo"]), label="Filo iluminado")
    g = toon(N, L, ng, 200, 300, col, 0.0, 0.9)
    t = nd(N, "ShaderNodeBsdfTransparent", 200, 50)
    mix = nd(N, "ShaderNodeMixShader", 450, 200)
    L.new(c1, mix.inputs[0])
    L.new(t.outputs[0], mix.inputs[1])
    L.new(g.outputs["Shader"], mix.inputs[2])
    salida(N, L, mix.outputs[0], 650, 200)
    return m


def mat_luz_techo():
    m, N, L = nuevo_material(PREFIJO + "Luz techo")
    e = nd(N, "ShaderNodeEmission", 0, 0)
    e.inputs["Color"].default_value = lin(PALETA["luz_techo"])
    e.inputs["Strength"].default_value = 5.0
    salida(N, L, e.outputs[0], 200, 0)
    return m


def mat_techo(ng):
    m, N, L = nuevo_material(PREFIJO + "Techo")
    salida(N, L, toon(N, L, ng, 0, 0, lin(PALETA["techo"]), 0.0, 1.1).outputs["Shader"], 250, 0)
    return m


# =====================================================================
#  Cielo: el mismo degradado y sol pintado de toon_atardecer.py
# =====================================================================
def construir_mundo(scene):
    w = bpy.data.worlds.get(MUNDO) or bpy.data.worlds.new(MUNDO)
    if w.node_tree is None:
        w.use_nodes = True
    N, L = w.node_tree.nodes, w.node_tree.links
    N.clear()
    tc = nd(N, "ShaderNodeTexCoord", -1400, 0)
    d = vmath(N, L, -1200, 0, "NORMALIZE", tc.outputs["Generated"])
    sep = nd(N, "ShaderNodeSeparateXYZ", -1000, 200)
    L.new(d, sep.inputs[0])
    z = sep.outputs["Z"]

    def zpos(zz):
        return (zz + 0.2) / 1.2
    t = mapr(N, L, -800, 300, z, -0.2, 1.0)
    grad = ramp(N, -600, 300, [
        (zpos(-0.20), "#1c0f2e"), (zpos(-0.02), "#3a1a40"), (zpos(0.00), "#ffcf7a"),
        (zpos(0.04), "#ff9f45"), (zpos(0.12), "#ff6a55"), (zpos(0.25), "#d44a7a"),
        (zpos(0.45), "#7a3488"), (zpos(0.70), "#33236a"), (zpos(1.00), "#15123a"),
    ], "LINEAR", "Colores del cielo")
    L.new(t, grad.inputs["Fac"])
    cielo = grad.outputs["Color"]

    cerca = vmath(N, L, -1000, -200, "DOT_PRODUCT", d, tuple(dir_sol()))
    horizonte = mapr(N, L, -800, -500, z, -0.004, 0.004)
    glow = mapr(N, L, -800, -100, cerca, 0.70, 1.0, interp="SMOOTHSTEP")
    glow = math_(N, L, -600, -100, "MULTIPLY", math_(N, L, -700, -50, "POWER", glow, 2.5), 0.55)
    glow = math_(N, L, -450, -150, "MULTIPLY", glow, mapr(N, L, -600, -200, z, -0.03, 0.01))
    cielo = mixc(N, L, -250, 250, glow, cielo, lin("#ffb066"), blend="SCREEN", label="Resplandor")
    tsol = mapr(N, L, -800, -300, cerca, 0.97, 1.0)
    halos = ramp(N, -600, -300, [(0.0, "#000000"), (0.50, "#ffb35c"), (0.75, "#ffc879"),
                                 (0.938, "#fff4d6")], "CONSTANT", "Sol y halos")
    for e_, a_ in zip(halos.color_ramp.elements, (0.0, 0.18, 0.38, 1.0)):
        e_.color = tuple(e_.color)[:3] + (a_,)
    L.new(tsol, halos.inputs["Fac"])
    a_sol = math_(N, L, -350, -380, "MULTIPLY", halos.outputs["Alpha"], horizonte)
    cielo = mixc(N, L, -50, 200, a_sol, cielo, halos.outputs["Color"], label="Sol")

    bg_cam = nd(N, "ShaderNodeBackground", 200, 150, "Cielo visible")
    L.new(cielo, bg_cam.inputs["Color"])
    bg_amb = nd(N, "ShaderNodeBackground", 200, -100, "Luz ambiente")
    L.new(grad.outputs["Color"], bg_amb.inputs["Color"])
    bg_amb.inputs["Strength"].default_value = LUZ_AMBIENTE
    lp = nd(N, "ShaderNodeLightPath", 200, 450)
    mix = nd(N, "ShaderNodeMixShader", 450, 0)
    L.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    L.new(bg_amb.outputs[0], mix.inputs[1])
    L.new(bg_cam.outputs[0], mix.inputs[2])
    out = nd(N, "ShaderNodeOutputWorld", 650, 0)
    L.new(mix.outputs[0], out.inputs["Surface"])
    w.color = lin("#ff9f45")[:3]
    scene.world = w
    return w


# =====================================================================
#  Compositor: solo Bloom (como material_bloom.py)
# =====================================================================
def construir_compositor(scene):
    if not hasattr(scene, "compositing_node_group"):
        return None
    tree = bpy.data.node_groups.get(COMPOSITOR) or \
        bpy.data.node_groups.new(COMPOSITOR, "CompositorNodeTree")
    tree.interface.clear()
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = tree
    N, L = tree.nodes, tree.links
    N.clear()
    rl = nd(N, "CompositorNodeRLayers", -400, 0)
    gl = nd(N, "CompositorNodeGlare", 0, 0, "Bloom")
    opcion(gl, "Type", ["Bloom", "BLOOM"])
    opcion(gl, "Quality", ["Medium", "MEDIUM"])
    opcion(gl, "Threshold", 1.2)
    opcion(gl, "Strength", 0.9)
    opcion(gl, "Size", 0.75)
    L.new(rl.outputs["Image"], gl.inputs["Image"])
    go = nd(N, "NodeGroupOutput", 300, 0)
    L.new(gl.outputs["Image"], go.inputs["Image"])
    v = nd(N, "CompositorNodeViewer", 300, -200)
    L.new(gl.outputs["Image"], v.inputs["Image"])
    return tree


# =====================================================================
#  3. Mallas base (low-poly) para instanciar
# =====================================================================
def caja(v, f, x0, x1, y0, y1, z0, z1, tapa_abajo=False):
    b = len(v)
    v += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
          (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f += [(b, b + 1, b + 5, b + 4), (b + 1, b + 2, b + 6, b + 5), (b + 2, b + 3, b + 7, b + 6),
          (b + 3, b, b + 4, b + 7), (b + 4, b + 5, b + 6, b + 7)]
    if tapa_abajo:
        f.append((b + 3, b + 2, b + 1, b))


def prisma(v, f, r, lados, z0, z1, punta=None, rot=0.0):
    b = len(v)
    for i in range(lados):
        a = rot + 2 * math.pi * i / lados
        v.append((r * math.cos(a), r * math.sin(a), z0))
    for i in range(lados):
        a = rot + 2 * math.pi * i / lados
        v.append((r * math.cos(a), r * math.sin(a), z1))
    for i in range(lados):
        j = (i + 1) % lados
        f.append((b + i, b + j, b + lados + j, b + lados + i))
    if punta is None:
        f.append(tuple(b + lados + i for i in range(lados)))
    else:
        v.append((0, 0, punta))
        c = len(v) - 1
        for i in range(lados):
            j = (i + 1) % lados
            f.append((b + lados + i, b + lados + j, c))


def cono(v, f, r, lados, z0, z1, base=True):
    b = len(v)
    for i in range(lados):
        a = 2 * math.pi * i / lados
        v.append((r * math.cos(a), r * math.sin(a), z0))
    v.append((0, 0, z1))
    c = len(v) - 1
    for i in range(lados):
        f.append((b + i, b + (i + 1) % lados, c))
    if base:
        f.append(tuple(reversed(range(b, b + lados))))


def malla(nombre, v, f, mat, col, suave=False):
    me = bpy.data.meshes.new(PREFIJO + nombre)
    me.from_pydata(v, [], f)
    me.validate()
    for p in me.polygons:
        p.use_smooth = suave
    me.materials.append(mat)
    ob = bpy.data.objects.new(PREFIJO + nombre, me)
    col.objects.link(ob)
    return ob


def fuentes_edificios(col, mat):
    """Unidad: planta 1x1 centrada, de z=0 (techo) a z=1 (punta)."""
    defs = []
    v, f = [], []                                   # 0: bloque simple (también LOD)
    caja(v, f, -.5, .5, -.5, .5, 0, 1)
    defs.append(("Edif 0 bloque", v, f))
    v, f = [], []                                   # 1: torre escalonada
    caja(v, f, -.5, .5, -.5, .5, 0, .62)
    caja(v, f, -.38, .38, -.38, .38, .62, .86)
    caja(v, f, -.24, .24, -.24, .24, .86, 1.0)
    defs.append(("Edif 1 escalonada", v, f))
    v, f = [], []                                   # 2: torre con aguja
    caja(v, f, -.42, .42, -.42, .42, 0, .8)
    caja(v, f, -.3, .3, -.3, .3, .8, .86)
    cono(v, f, .12, 4, .86, 1.0, base=False)
    defs.append(("Edif 2 aguja", v, f))
    v, f = [], []                                   # 3: torre octogonal con corona
    prisma(v, f, .5, 8, 0, .88, rot=math.pi / 8)
    prisma(v, f, .36, 8, .88, .97, punta=1.0, rot=math.pi / 8)
    defs.append(("Edif 3 octogonal", v, f))
    v, f = [], []                                   # 4: torres gemelas
    caja(v, f, -.5, -.05, -.5, .5, 0, 1.0)
    caja(v, f, .05, .5, -.5, .5, 0, .82)
    caja(v, f, -.05, .05, -.2, .2, .3, .36)         # pasarela
    defs.append(("Edif 4 gemelas", v, f))
    v, f = [], []                                   # 5: bloque en L
    caja(v, f, -.5, .5, -.5, 0, 0, .7)
    caja(v, f, -.5, 0, 0, .5, 0, 1.0)
    defs.append(("Edif 5 L", v, f))
    return [malla(n, v, f, mat, col) for n, v, f in defs]


def fuentes_arboles(col, mat):
    defs = []
    v, f = [], []                                   # 0: pino de 3 pisos
    prisma(v, f, .06, 4, 0, .25)
    cono(v, f, .42, 6, .15, .6)
    cono(v, f, .33, 6, .42, .82)
    cono(v, f, .22, 6, .65, 1.0)
    defs.append(("Arbol 0 pino", v, f, False))
    v, f = [], []                                   # 1: pino alto
    cono(v, f, .3, 6, 0.05, 1.0)
    cono(v, f, .36, 6, 0.0, .55)
    defs.append(("Arbol 1 alto", v, f, False))
    bm = bmesh.new()                                # 2: copa redonda
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.42)
    bmesh.ops.translate(bm, vec=(0, 0, 0.55), verts=bm.verts)
    bmesh.ops.scale(bm, vec=(1, 1, 0.85), verts=bm.verts)
    v2 = [tuple(x.co) for x in bm.verts]
    f2 = [tuple(x.index for x in p.verts) for p in bm.faces]
    bm.free()
    prisma(v2, f2, .05, 4, 0, .3)
    defs.append(("Arbol 2 redondo", v2, f2, True))
    v, f = [], []                                   # 3: LOD lejano (4 caras)
    cono(v, f, .35, 4, 0, 1.0, base=False)
    defs.append(("Arbol 3 lejano", v, f, False))
    return [malla(n, v, f, mat, col, s) for n, v, f, s in defs]


def fuente_placa(col, mat):
    v = [(-.5, -.5, 0), (.5, -.5, 0), (.5, .5, 0), (-.5, .5, 0)]
    return malla("Placa luz", v, [(3, 2, 1, 0)], mat, col)


# =====================================================================
#  4. Geometry Nodes: instanciar en puntos con atributos
# =====================================================================
def gn_instanciar(nombre, coleccion):
    ng = bpy.data.node_groups.get(nombre)
    if ng:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(nombre, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    try:
        ng.is_modifier = True
    except Exception:
        pass
    N, L = ng.nodes, ng.links
    gi = nd(N, "NodeGroupInput", -800, 0)
    go = nd(N, "NodeGroupOutput", 400, 0)
    ci = nd(N, "GeometryNodeCollectionInfo", -500, -200)
    ci.transform_space = "ORIGINAL"
    ci.inputs["Collection"].default_value = coleccion
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    t = nd(N, "GeometryNodeInputNamedAttribute", -500, -400, data_type="INT")
    t.inputs["Name"].default_value = "tipo"
    r = nd(N, "GeometryNodeInputNamedAttribute", -700, -550, data_type="FLOAT_VECTOR")
    r.inputs["Name"].default_value = "rot"
    e2r = nd(N, "FunctionNodeEulerToRotation", -500, -550)
    L.new(r.outputs["Attribute"], e2r.inputs[0])
    s = nd(N, "GeometryNodeInputNamedAttribute", -500, -700, data_type="FLOAT_VECTOR")
    s.inputs["Name"].default_value = "esc"
    ip = nd(N, "GeometryNodeInstanceOnPoints", 0, 0)
    ip.inputs["Pick Instance"].default_value = True
    L.new(gi.outputs[0], ip.inputs["Points"])
    L.new(ci.outputs[0], ip.inputs["Instance"])
    L.new(t.outputs["Attribute"], ip.inputs["Instance Index"])
    L.new(e2r.outputs[0], ip.inputs["Rotation"])
    L.new(s.outputs["Attribute"], ip.inputs["Scale"])
    L.new(ip.outputs[0], go.inputs[0])
    return ng


def nube_de_puntos(nombre, puntos, col, raiz, gn):
    """puntos: lista de (pos, tipo, rot_euler, escala)."""
    me = bpy.data.meshes.new(PREFIJO + nombre)
    me.from_pydata([p[0] for p in puntos], [], [])
    a = me.attributes.new("tipo", "INT", "POINT")
    a.data.foreach_set("value", [p[1] for p in puntos])
    a = me.attributes.new("rot", "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", [c for p in puntos for c in p[2]])
    a = me.attributes.new("esc", "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", [c for p in puntos for c in p[3]])
    ob = bpy.data.objects.new(PREFIJO + nombre, me)
    col.objects.link(ob)
    ob.parent = raiz
    mod = ob.modifiers.new("Instancias", "NODES")
    mod.node_group = gn
    sin_sombras(ob)
    return ob


def sin_sombras(ob):
    for attr in ("visible_shadow",):
        try:
            setattr(ob, attr, False)
        except Exception:
            pass


# =====================================================================
#  5. Terreno: función de altura + malla radial (LOD por distancia)
# =====================================================================
def mascara_lago(x, y):
    """<0 dentro del lago, >0 en tierra."""
    dx, dy = x - LAGO["cx"], y - LAGO["cy"]
    rx = LAGO["rx_izq"] if dx < 0 else LAGO["rx_der"]
    w = noise.noise(Vector((x * 0.0016, y * 0.0016, 1.7))) * 0.22 \
        + noise.noise(Vector((x * 0.006, y * 0.006, 4.1))) * 0.05
    return math.sqrt((dx / rx) ** 2 + (dy / LAGO["ry"]) ** 2) + w - 1.0


def altura(x, y):
    t = mascara_lago(x, y)
    if t < 0:
        h = -10.0 * min(1.0, -t * 5.0)
    else:
        orilla = smooth(0.0, 0.45, t)
        d = math.hypot(x - LAGO["cx"], y - LAGO["cy"])
        amp = 90.0 + 560.0 * smooth(1000.0, 3600.0, d)
        p = Vector((x * 0.0011, y * 0.0011, 0.0))
        m = noise.ridged_multi_fractal(p, 1.0, 2.0, 5, 1.0, 2.0) * 0.5
        det = noise.fractal(p * 6.0, 0.6, 2.0, 3) * 0.12
        h = 1.5 + orilla * amp * max(0.05, m * 0.85 + det + 0.1)
        for px, py, ph, pr in PICOS:
            dp = math.hypot(x - px, y - py) / pr
            if dp < 3.0:
                # perfil en "cono" con crestas: picos afilados en vez de cúpulas
                g = math.exp(-dp * 1.6) * smooth(3.0, 0.4, dp)
                cr = noise.ridged_multi_fractal(Vector((x * 0.003, y * 0.003, px * 0.01)),
                                                0.9, 2.1, 5, 1.0, 2.0) * 0.5
                h += ph * g * (0.55 + 0.6 * cr) * smooth(0.0, 0.3, t)
    di = math.hypot(x - ISLA["x"], (y - ISLA["y"]) * 1.35)
    if di < ISLA["r"]:
        k = 1.0 - (di / ISLA["r"]) ** 2
        hi = ISLA["alto"] * k + noise.noise(Vector((x * 0.03, y * 0.03, 9.0))) * 2.5 * k - 1.5
        h = max(h, hi)
    return h


def crear_terreno(col, raiz, mat):
    random.seed(SEMILLA)
    anillos, sectores = 100, 220
    r0, r1 = 25.0, 8000.0
    radios = [r0 * (r1 / r0) ** (i / (anillos - 1)) for i in range(anillos)]
    cx, cy = 0.0, 600.0                       # centro del LOD (algo por delante del EVA)
    v, f = [], []
    for r in radios:
        for j in range(sectores):
            a = 2 * math.pi * j / sectores
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            v.append((x * TAMANO_MUNDO, y * TAMANO_MUNDO, altura(x, y) * TAMANO_MUNDO))
    for i in range(anillos - 1):
        for j in range(sectores):
            a0, a1 = i * sectores + j, i * sectores + (j + 1) % sectores
            f.append((a0, a1, a1 + sectores, a0 + sectores))
    ob = malla("Terreno", v, f, mat, col)   # facetado = look low-poly toon
    ob.parent = raiz
    sin_sombras(ob)
    return ob


def crear_agua(col, raiz, mat):
    s = 9000.0 * TAMANO_MUNDO
    v = [(-s, -s + 2000, 0), (s, -s + 2000, 0), (s, s, 0), (-s, s, 0)]
    ob = malla("Lago", v, [(0, 1, 2, 3)], mat, col)
    ob.parent = raiz
    sin_sombras(ob)
    return ob


def puntos_arboles():
    rnd = random.Random(SEMILLA + 1)
    pts = []
    intentos = 0
    cam = POS_CAMARA
    while len(pts) < NUM_ARBOLES and intentos < NUM_ARBOLES * 14:
        intentos += 1
        # muestreo más denso cerca de la cámara (LOD)
        d = 60.0 + (DISTANCIA_ARBOLES - 60.0) * rnd.random() ** 1.6
        a = math.radians(rnd.uniform(-75, 75))
        x, y = cam.x + d * math.sin(a), cam.y + d * math.cos(a)
        h = altura(x, y)
        isla = math.hypot(x - ISLA["x"], (y - ISLA["y"]) * 1.35) < ISLA["r"] * 0.95
        if h < 1.2 or h > 330.0:
            continue
        if isla and math.hypot(x - ISLA["x"], y - ISLA["y"]) < PIRAMIDE_BASE * 0.62:
            continue
        e = 6.0
        pend = math.hypot(altura(x + e, y) - h, altura(x, y + e) - h) / e
        if pend > 0.9:
            continue
        if rnd.random() < 0.35 * smooth(150.0, 330.0, h):
            continue
        bosque = noise.noise(Vector((x * 0.004, y * 0.004, 3.3)))
        if not isla and bosque < -0.35 and rnd.random() < 0.7:
            continue                               # claros en el bosque
        alto = rnd.uniform(9.0, 18.0) * (1.25 if isla else 1.0)
        if d > 1100.0:
            tipo = 3
            alto *= 1.4                            # los lejanos un poco más grandes (se leen mejor)
        elif isla:
            tipo = 2
        else:
            tipo = rnd.choice((0, 0, 1, 1, 2))
        ancho = alto * rnd.uniform(0.75, 1.05)
        pos = (x * TAMANO_MUNDO, y * TAMANO_MUNDO, (h - 0.6) * TAMANO_MUNDO)
        rot = (rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), rnd.uniform(0, 6.283))
        pts.append((pos, tipo, rot, (ancho * TAMANO_MUNDO,) * 2 + (alto * TAMANO_MUNDO,)))
    return pts


def puntos_edificios():
    rnd = random.Random(SEMILLA + 2)
    pts = []
    celda = 54.0
    nx, ny = int(CIUDAD["rx"] * 2 / celda), int(CIUDAD["ry"] * 2 / celda)
    celdas = []
    for i in range(nx):
        for j in range(ny):
            x = CIUDAD["cx"] - CIUDAD["rx"] + (i + 0.5) * celda
            y = CIUDAD["cy"] - CIUDAD["ry"] + (j + 0.5) * celda
            r = math.hypot((x - CIUDAD["cx"]) / CIUDAD["rx"], (y - CIUDAD["cy"]) / CIUDAD["ry"])
            r += noise.noise(Vector((x * 0.002, y * 0.002, 7.0))) * 0.25
            if r > 1.0 or (i % 5 == 2) or (j % 6 == 3):     # avenidas
                continue
            celdas.append((x, y, r))
    rnd.shuffle(celdas)
    for x, y, r in celdas:
        if len(pts) >= NUM_EDIFICIOS:
            break
        if rnd.random() > 0.35 + 0.65 * (1 - r):
            continue
        centro = 1.0 - r
        largo = LARGO_MAX_EDIFICIO * (0.12 + 0.88 * centro ** 1.3 * rnd.random() ** 0.8)
        largo = max(45.0, largo)
        w = rnd.uniform(26.0, 46.0)
        dd = rnd.uniform(26.0, 46.0)
        if largo > 260:
            tipo = rnd.choice((1, 2, 2, 3, 4))
        elif largo > 120:
            tipo = rnd.choice((0, 1, 3, 5, 5))
        else:
            tipo = rnd.choice((0, 0, 5))
        dist = (Vector((x, y, ALTURA_TECHO)) - POS_CAMARA).length
        if dist > 3900.0:
            tipo = 0                                 # LOD lejano: bloque simple
        z = ALTURA_TECHO + rnd.uniform(-8.0, 6.0)
        pos = (x * TAMANO_MUNDO, y * TAMANO_MUNDO, z * TAMANO_MUNDO)
        rot = (math.pi, 0.0, rnd.randint(0, 3) * math.pi / 2)
        pts.append((pos, tipo, rot, (w * TAMANO_MUNDO, dd * TAMANO_MUNDO, largo * TAMANO_MUNDO)))
    return pts


def puntos_luces_techo():
    rnd = random.Random(SEMILLA + 3)
    pts = []
    for _ in range(NUM_LUCES_TECHO):
        x = rnd.uniform(-1800, 1800)
        y = rnd.uniform(500, 3800)
        z = ALTURA_TECHO - rnd.uniform(40, 330)
        pos = (x * TAMANO_MUNDO, y * TAMANO_MUNDO, z * TAMANO_MUNDO)
        rot = (0.0, 0.0, rnd.uniform(-0.2, 0.2))
        s = rnd.uniform(6, 13)
        pts.append((pos, 0, rot, (s * 2.8 * TAMANO_MUNDO, s * TAMANO_MUNDO, 1.0)))
    return pts


# =====================================================================
#  6. Pirámide, nubes del techo y rayos de luz
# =====================================================================
def crear_piramide(col, raiz, mat):
    v, f = [], []
    cono(v, f, 1.0 / math.sqrt(2), 4, 0.0, 1.0)
    for i, p in enumerate(v):
        x, y, z = p
        c, s = math.cos(math.pi / 4), math.sin(math.pi / 4)
        v[i] = (x * c - y * s, x * s + y * c, z)
    ob = malla("Piramide", v, f, mat, col)
    ob.parent = raiz
    h = altura(ISLA["x"], ISLA["y"])
    ob.location = (ISLA["x"] * TAMANO_MUNDO, ISLA["y"] * TAMANO_MUNDO, (h - 3.0) * TAMANO_MUNDO)
    ob.scale = (PIRAMIDE_BASE * TAMANO_MUNDO, PIRAMIDE_BASE * TAMANO_MUNDO, PIRAMIDE_ALTO * TAMANO_MUNDO)
    sin_sombras(ob)
    return ob


def plano_uv(nombre, ancho, largo, mat, col, abajo=True):
    """Plano en XZ (normal -Y). Si abajo: cuelga de z=0 a z=-largo."""
    z0, z1 = (-largo, 0.0) if abajo else (0.0, largo)
    v = [(-ancho / 2, 0, z0), (ancho / 2, 0, z0), (ancho / 2, 0, z1), (-ancho / 2, 0, z1)]
    ob = malla(nombre, v, [(0, 1, 2, 3)], mat, col)
    uv = ob.data.uv_layers.new(name="UVMap")
    for li, (uu, vv) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (uu, vv)
    return ob


def crear_rayos(col, raiz, mat, cam):
    rnd = random.Random(SEMILLA + 4)
    obs = []
    for i in range(NUM_RAYOS):
        x = rnd.uniform(-1300, 1300)
        y = rnd.uniform(700, 2700)
        ancho = rnd.uniform(40, 170)
        largo = ALTURA_TECHO * rnd.uniform(1.05, 1.35)
        ob = plano_uv("Rayo %02d" % i, ancho * TAMANO_MUNDO, largo * TAMANO_MUNDO, mat, col)
        ob.parent = raiz
        ob.location = (x * TAMANO_MUNDO, y * TAMANO_MUNDO, (ALTURA_TECHO - 60) * TAMANO_MUNDO)
        # inclinados como si vinieran de arriba a la derecha; giran para mirar a cámara
        ob.rotation_euler = (0.0, math.radians(rnd.uniform(14, 24)), 0.0)
        if cam is not None:
            c = ob.constraints.new("LOCKED_TRACK")
            c.target = cam
            c.track_axis = "TRACK_NEGATIVE_Y"
            c.lock_axis = "LOCK_Z"
        sin_sombras(ob)
        obs.append(ob)
    return obs


def crear_nubes_techo(col, raiz, mat):
    obs = []
    for i, (z, s) in enumerate(((ALTURA_TECHO - 15, 1.0), (ALTURA_TECHO - 70, 0.9),
                                 (ALTURA_TECHO - 140, 0.75))):
        a, b = CIUDAD["rx"] * 1.25 * s, CIUDAD["ry"] * 1.3 * s      # semiejes
        v = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)]
        ob = malla("Nubes techo %d" % i, v, [(3, 2, 1, 0)], mat, col)
        ob.parent = raiz
        ob.location = (CIUDAD["cx"] * TAMANO_MUNDO, CIUDAD["cy"] * TAMANO_MUNDO, z * TAMANO_MUNDO)
        ob.scale = (a * TAMANO_MUNDO, b * TAMANO_MUNDO, 1.0)
        sin_sombras(ob)
        obs.append(ob)
    return obs


def crear_techo(col, raiz, mat):
    """Bóveda del techo: rejilla con algo de ruido, solo detrás de la ciudad."""
    n, s = 40, 9000.0
    v, f = [], []
    for i in range(n + 1):
        for j in range(n + 1):
            x = -s / 2 + s * i / n
            y = -1500 + s * j / n
            z = ALTURA_TECHO + 25 + noise.noise(Vector((x * 0.001, y * 0.001, 2.0))) * 40
            v.append((x * TAMANO_MUNDO, y * TAMANO_MUNDO, z * TAMANO_MUNDO))
    for i in range(n):
        for j in range(n):
            a = i * (n + 1) + j
            f.append((a, a + n + 1, a + n + 2, a + 1))
    ob = malla("Techo", v, f, mat, col)
    ob.parent = raiz
    sin_sombras(ob)
    return ob



# =====================================================================
#  Escena, cámara y render
# =====================================================================
def objetos_modelo(scene, excluir):
    return [o for o in scene.objects if o.type in {"MESH", "CURVE"} and o.visible_get()
            and o.name not in excluir and not o.name.startswith(PREFIJO)]


def caja_mundo(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        oe = o.evaluated_get(dg)
        pts += [oe.matrix_world @ Vector(c) for c in oe.bound_box]
    if not pts:
        return Vector((-1, -1, 0)), Vector((1, 1, 2))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def borrar_anterior():
    col = bpy.data.collections.get(COL)
    if col:
        for c in list(col.children_recursive):
            for o in list(c.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(c)
        for o in list(col.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.name.startswith(PREFIJO) and me.users == 0:
            bpy.data.meshes.remove(me)
    return col


def colecciones(scene):
    col = bpy.data.collections.get(COL) or bpy.data.collections.new(COL)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    fuentes = {}
    for nombre in ("Edificios", "Arboles", "Placas"):
        c = bpy.data.collections.new("%s %s" % (COL_FUENTES, nombre))
        col.children.link(c)
        fuentes[nombre] = c

    def excluir(lc):
        for ch in lc.children:
            if ch.collection.name.startswith(COL_FUENTES):
                ch.exclude = True
            excluir(ch)
    for vl in scene.view_layers:
        excluir(vl.layer_collection)
    return col, fuentes


def crear_camara(scene, raiz):
    if scene.camera is not None or not CREAR_CAMARA:
        return scene.camera
    data = bpy.data.cameras.get(CAM) or bpy.data.cameras.new(CAM)
    data.lens = 18
    data.clip_start = 0.1
    data.clip_end = 30000.0 * TAMANO_MUNDO
    cam = bpy.data.objects.get(CAM) or bpy.data.objects.new(CAM, data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    m = raiz.matrix_world
    pos = m @ POS_CAMARA
    mira = m @ Vector((MIRA_CAMARA.x * TAMANO_MUNDO, MIRA_CAMARA.y * TAMANO_MUNDO,
                       MIRA_CAMARA.z * TAMANO_MUNDO))
    cam.location = pos
    cam.rotation_euler = (mira - pos).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return cam


def ajustes_render(scene):
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except Exception:
        pass
    e = scene.eevee
    for attr, val in (("taa_render_samples", 16), ("taa_samples", 8),
                      ("use_raytracing", REFLEJOS_AGUA), ("ray_tracing_method", "SCREEN"),
                      ("use_fast_gi", False), ("shadow_resolution_scale", 0.75)):
        try:
            setattr(e, attr, val)
        except Exception:
            pass
    try:
        e.ray_tracing_options.resolution_scale = "2"
        e.ray_tracing_options.trace_max_roughness = 0.2
    except Exception:
        pass
    vs = scene.view_settings
    try:
        vs.view_transform = "Standard"
        vs.look = "None"
    except Exception:
        pass
    scene.render.film_transparent = False
    scene.render.use_compositing = True


def vista_renderizada():
    try:
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    for sp in area.spaces:
                        if sp.type == "VIEW_3D":
                            sp.clip_end = max(sp.clip_end, 30000.0 * TAMANO_MUNDO)
                            sp.shading.type = "RENDERED"
                            try:
                                sp.shading.use_compositor = "ALWAYS"
                            except Exception:
                                pass
    except Exception:
        pass




# =====================================================================
#  main
# =====================================================================
def ocultar_v1(scene):
    def rec(lc):
        for ch in lc.children:
            if ch.collection.name == COL_V1:
                ch.exclude = True
            rec(ch)
    for vl in scene.view_layers:
        rec(vl.layer_collection)


def main():
    scene = bpy.context.scene
    borrar_anterior()
    ocultar_v1(scene)
    col, fuentes = colecciones(scene)

    modelo = [o for o in objetos_modelo(scene, set()) if not o.name.startswith("GF ")]
    lo, hi = caja_mundo(modelo)
    raiz = bpy.data.objects.get(RAIZ)
    if raiz is None:
        raiz = bpy.data.objects.new(RAIZ, None)
        raiz.empty_display_type = "PLAIN_AXES"
        raiz.empty_display_size = 20
        raiz.location = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z + NIVEL_AGUA)
    for c in raiz.users_collection:
        c.objects.unlink(raiz)
    col.objects.link(raiz)
    bpy.context.view_layer.update()

    ng = grupo_toon()
    m_ter, m_arb, m_edi = mat_terreno(ng), mat_arbol(ng), mat_edificio(ng)
    m_pir, m_agua, m_rayo = mat_piramide(ng), mat_agua(ng), mat_rayo()
    m_nube, m_luz, m_techo = mat_nube(ng), mat_luz_techo(), mat_techo(ng)

    crear_terreno(col, raiz, m_ter)
    crear_agua(col, raiz, m_agua)
    crear_piramide(col, raiz, m_pir)
    crear_techo(col, raiz, m_techo)

    fuentes_edificios(fuentes["Edificios"], m_edi)
    fuentes_arboles(fuentes["Arboles"], m_arb)
    fuente_placa(fuentes["Placas"], m_luz)
    gn_e = gn_instanciar("GT Instanciar edificios", fuentes["Edificios"])
    gn_a = gn_instanciar("GT Instanciar arboles", fuentes["Arboles"])
    gn_l = gn_instanciar("GT Instanciar luces", fuentes["Placas"])
    pe, pa, pl = puntos_edificios(), puntos_arboles(), puntos_luces_techo()
    nube_de_puntos("Ciudad colgante", pe, col, raiz, gn_e)
    nube_de_puntos("Bosque", pa, col, raiz, gn_a)
    nube_de_puntos("Luces techo", pl, col, raiz, gn_l)
    crear_nubes_techo(col, raiz, m_nube)

    bpy.context.view_layer.update()
    cam = crear_camara(scene, raiz)
    crear_rayos(col, raiz, m_rayo, cam)

    if USAR_MUNDO:
        construir_mundo(scene)
    if AJUSTES_RENDER:
        ajustes_render(scene)
    if USAR_COMPOSITOR:
        construir_compositor(scene)
    vista_renderizada()
    print("Geofront toon listo: %d edificios, %d árboles, %d luces, %d rayos (instancias)."
          % (len(pe), len(pa), len(pl), NUM_RAYOS))


main()
