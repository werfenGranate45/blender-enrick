# =====================================================================
#  ESTILO CARTOON + CIELO DE ATARDECER  —  para EVANGELION.blend (Blender 5.1)
#
#  Cómo usarlo:
#    1. Abre EVANGELION.blend en Blender.
#    2. Ve a la pestaña "Scripting", pulsa "Abrir" y elige este archivo.
#    3. Pulsa ▶ (Ejecutar script).  Ctrl+Z lo deshace todo de un golpe.
#    4. Guarda con "Guardar como..." si quieres conservar el original.
#
#  Qué hace:
#    • Cada material conserva su color exacto (lado iluminado = color original)
#      y recibe sombreado por bandas tipo anime, sombra con tinte morado de
#      atardecer, brillo especular duro y luz de borde naranja.
#    • Cielo de atardecer estilizado: degradado, sol poniéndose con halos y
#      nubes de dos tonos.
#    • Una luz de sol (necesaria para que se formen las sombras cartoon) y
#      gestión de color "Standard" para que los colores no se laven.
#    • Si ya habías corrido la versión anterior, quita el contorno, la cámara
#      "Camara Cartoon" y vuelve a mostrar las esferas en el render.
#    • NO toca la geometría: el contorno viene desactivado (CONTORNO = False).
#
#  Todo el sombreado vive en el grupo de nodos "Toon Cartoon": si cambias las
#  bandas ahí, cambian todos los materiales a la vez.  Funciona con EEVEE
#  (el nodo Shader to RGB no existe en Cycles).
# =====================================================================

import bpy
import math
from mathutils import Vector

# ---------------------------- AJUSTES --------------------------------
CONTORNO = False              # contorno negro (modificador Solidify); apagado
GROSOR_CONTORNO = 0.004       # fracción del tamaño del modelo
COLOR_CONTORNO = "#1e1028"    # morado casi negro

TINTE_SOMBRA = "#b4a5cf"      # multiplica el color en la sombra (morado = atardecer)
UMBRAL_MEDIO = 0.10           # dónde empieza la banda media
UMBRAL_LUZ = 0.30             # dónde empieza la banda iluminada
COLOR_BORDE = "#ffa04d"       # luz de borde (rim) naranja
FUERZA_BORDE = 0.6
COLOR_BRILLO = "#fff2d6"
FUERZA_BRILLO = 0.35

LUZ_FUERZA = 3.0              # sol principal (solo define dónde caen las bandas)
LUZ_COLOR = "#ffd2a6"
LUZ_AZIMUT = 35.0             # grados: 0 = de frente, + = desde la izquierda
LUZ_ELEVACION = 22.0
LUZ_AMBIENTE = 0.15           # cuánto ilumina el cielo (bajo = sombras más marcadas)

SOL_CIELO_AZIMUT = 14.0       # sol pintado en el cielo, detrás del modelo
SOL_CIELO_ELEVACION = 4.0     # bajo = medio escondido en el horizonte
GIRO_CIELO = 0.0              # grados, gira todo el cielo
NUBES = True

CREAR_CAMARA = False          # crear cámara si la escena no tiene
OCULTAR_ESFERAS_EN_RENDER = False  # ocultar las esferas de paleta en el render
# ---------------------------------------------------------------------

GRUPO = "Toon Cartoon"
MAT_CONTORNO = "Contorno Cartoon"
MOD_CONTORNO = "Contorno Cartoon"
NODO_TOON = "Cartoon"


def lin(hexstr, a=1.0):
    """Color hex (sRGB, como en el selector de color) -> RGBA lineal."""
    h = hexstr.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], a)


def sock(coll, name, typ=None):
    """Busca un socket por nombre (y tipo), prefiriendo los que están activos."""
    cands = [s for s in coll if s.name == name and (typ is None or s.type == typ)]
    for s in cands:
        if getattr(s, "enabled", True) and not getattr(s, "is_unavailable", False):
            return s
    if cands:
        return cands[0]
    for s in coll:
        if s.identifier == name:
            return s
    raise KeyError(f"Socket '{name}' no encontrado")


def nd(nodes, idname, x, y, label=None, **props):
    n = nodes.new(idname)
    n.location = (x, y)
    if label:
        n.label = label
    for k, v in props.items():
        setattr(n, k, v)
    return n


def glossy(nodes, x, y):
    for idn in ("ShaderNodeBsdfGlossy", "ShaderNodeBsdfAnisotropic"):
        try:
            return nd(nodes, idn, x, y)
        except Exception:
            pass
    raise RuntimeError("No se pudo crear el nodo Glossy")


def mix_color(nodes, links, x, y, blend, fac, a, b, label=None):
    """Nodo Mix en modo color. fac/a/b pueden ser sockets o valores."""
    n = nd(nodes, "ShaderNodeMix", x, y, label)
    n.data_type = "RGBA"
    n.blend_type = blend
    n.clamp_result = True
    for s, v in ((sock(n.inputs, "Factor", "VALUE"), fac),
                 (sock(n.inputs, "A", "RGBA"), a),
                 (sock(n.inputs, "B", "RGBA"), b)):
        if isinstance(v, bpy.types.NodeSocket):
            links.new(v, s)
        else:
            s.default_value = v
    return n, sock(n.outputs, "Result", "RGBA")


def math_node(nodes, links, x, y, op, a, b=0.0, label=None, clamp=False):
    n = nd(nodes, "ShaderNodeMath", x, y, label)
    n.operation = op
    n.use_clamp = clamp
    for s, v in ((n.inputs[0], a), (n.inputs[1], b)):
        if isinstance(v, bpy.types.NodeSocket):
            links.new(v, s)
        else:
            s.default_value = v
    return n.outputs[0]


def map_range(nodes, links, x, y, value, fmin, fmax, tmin=0.0, tmax=1.0,
              interp="LINEAR", label=None):
    n = nd(nodes, "ShaderNodeMapRange", x, y, label)
    n.data_type = "FLOAT"
    n.interpolation_type = interp
    n.clamp = True
    links.new(value, sock(n.inputs, "Value", "VALUE"))
    sock(n.inputs, "From Min", "VALUE").default_value = fmin
    sock(n.inputs, "From Max", "VALUE").default_value = fmax
    sock(n.inputs, "To Min", "VALUE").default_value = tmin
    sock(n.inputs, "To Max", "VALUE").default_value = tmax
    return sock(n.outputs, "Result", "VALUE")


def ramp(nodes, x, y, stops, interp="CONSTANT", label=None):
    """stops: lista ordenada de (posición, rgba)."""
    n = nd(nodes, "ShaderNodeValToRGB", x, y, label)
    cr = n.color_ramp
    cr.interpolation = interp
    el = cr.elements
    el[0].position, el[0].color = stops[0]
    el[1].position, el[1].color = stops[-1]
    for pos, col in stops[1:-1]:
        e = el.new(pos)
        e.color = col
    return n


# ------------------------------------------------------------------
# 1. Grupo de nodos con el sombreado cartoon (compartido)
# ------------------------------------------------------------------
def construir_grupo():
    ng = bpy.data.node_groups.get(GRUPO)
    if ng is None:
        ng = bpy.data.node_groups.new(GRUPO, "ShaderNodeTree")
    ng.nodes.clear()
    ng.interface.clear()

    def add_in(name, kind, default, lo=None, hi=None):
        s = ng.interface.new_socket(name=name, in_out="INPUT", socket_type=kind)
        s.default_value = default
        if lo is not None:
            s.min_value, s.max_value = lo, hi
        return s

    add_in("Color", "NodeSocketColor", (0.8, 0.8, 0.8, 1.0))
    add_in("Tinte sombra", "NodeSocketColor", lin(TINTE_SOMBRA))
    add_in("Color borde", "NodeSocketColor", lin(COLOR_BORDE))
    add_in("Fuerza borde", "NodeSocketFloat", FUERZA_BORDE, 0.0, 2.0)
    add_in("Fuerza brillo", "NodeSocketFloat", FUERZA_BRILLO, 0.0, 2.0)
    ng.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")

    N, L = ng.nodes, ng.links
    gin = nd(N, "NodeGroupInput", -1100, 0)
    gout = nd(N, "NodeGroupOutput", 1100, 0)
    c_in = gin.outputs["Color"]

    # --- Bandas de luz: cuánta luz recibe la superficie (incluye sombras proyectadas)
    dif = nd(N, "ShaderNodeBsdfDiffuse", -900, 300)
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nd(N, "ShaderNodeShaderToRGB", -700, 300)
    L.new(dif.outputs["BSDF"], s2r.inputs["Shader"])
    bw = nd(N, "ShaderNodeRGBToBW", -520, 300)
    L.new(s2r.outputs["Color"], bw.inputs["Color"])
    bandas = ramp(N, -340, 300, [
        (0.0, (0, 0, 0, 1)),
        (UMBRAL_MEDIO, (0.5, 0.5, 0.5, 1)),
        (UMBRAL_LUZ, (1, 1, 1, 1)),
    ], label="Bandas de luz (ajusta aquí)")
    L.new(bw.outputs["Val"], bandas.inputs["Fac"])
    luz = bandas.outputs["Color"]

    # --- Color en sombra = color original x tinte morado
    _, sombra = mix_color(N, L, -340, -60, "MULTIPLY", 1.0, c_in,
                          gin.outputs["Tinte sombra"], "Color en sombra")
    _, base = mix_color(N, L, 0, 120, "MIX", luz, sombra, c_in, "Sombra / luz")

    # --- Brillo especular duro
    gl = glossy(N, -900, -340)
    gl.inputs["Color"].default_value = (1, 1, 1, 1)
    gl.inputs["Roughness"].default_value = 0.3
    s2r2 = nd(N, "ShaderNodeShaderToRGB", -700, -340)
    L.new(gl.outputs["BSDF"], s2r2.inputs["Shader"])
    bw2 = nd(N, "ShaderNodeRGBToBW", -520, -340)
    L.new(s2r2.outputs["Color"], bw2.inputs["Color"])
    corte_brillo = ramp(N, -340, -340, [
        (0.0, (0, 0, 0, 1)), (0.9, (1, 1, 1, 1))], label="Tamaño del brillo")
    L.new(bw2.outputs["Val"], corte_brillo.inputs["Fac"])
    brillo = math_node(N, L, -60, -340, "MULTIPLY", corte_brillo.outputs["Color"],
                       gin.outputs["Fuerza brillo"])
    brillo = math_node(N, L, 120, -340, "MULTIPLY", brillo, luz)
    _, col = mix_color(N, L, 320, 60, "ADD", brillo, base, lin(COLOR_BRILLO), "Brillo")

    # --- Luz de borde (rim), solo en el lado que recibe luz
    lw = nd(N, "ShaderNodeLayerWeight", -900, -700)
    lw.inputs["Blend"].default_value = 0.5
    corte_borde = ramp(N, -700, -700, [
        (0.0, (0, 0, 0, 1)), (0.7, (1, 1, 1, 1))], label="Grosor del borde")
    L.new(lw.outputs["Facing"], corte_borde.inputs["Fac"])
    borde = math_node(N, L, -400, -700, "MULTIPLY", corte_borde.outputs["Color"],
                      gin.outputs["Fuerza borde"])
    borde = math_node(N, L, -200, -700, "MULTIPLY", borde, luz, clamp=True)
    _, col = mix_color(N, L, 600, 0, "SCREEN", borde, col,
                       gin.outputs["Color borde"], "Luz de borde")

    emi = nd(N, "ShaderNodeEmission", 850, 0)
    L.new(col, emi.inputs["Color"])
    emi.inputs["Strength"].default_value = 1.0
    L.new(emi.outputs["Emission"], gout.inputs["Shader"])
    return ng


# ------------------------------------------------------------------
# 2. Aplicar el grupo a cada material, conservando su color
# ------------------------------------------------------------------
def convertir_material(mat, ng):
    nt = mat.node_tree
    if nt is None:
        try:
            mat.use_nodes = True
        except Exception:
            pass
        nt = mat.node_tree
    if nt is None:
        return False
    N, L = nt.nodes, nt.links

    out = next((n for n in N if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
    out = out or next((n for n in N if n.type == "OUTPUT_MATERIAL"), None)
    if out is None:
        out = nd(N, "ShaderNodeOutputMaterial", 400, 0)

    pbsdf = next((n for n in N if n.type == "BSDF_PRINCIPLED"), None)

    g = N.get(NODO_TOON)
    if g is None:
        g = nd(N, "ShaderNodeGroup", out.location.x - 260, out.location.y - 260)
        g.name = NODO_TOON
        g.label = "Cartoon"
    g.node_tree = ng
    g.width = 200

    c = g.inputs["Color"]
    if pbsdf is not None:
        bc = pbsdf.inputs["Base Color"]
        if bc.is_linked:                       # textura conectada: se reutiliza
            L.new(bc.links[0].from_socket, c)
        else:
            c.default_value = tuple(bc.default_value)
        pbsdf.label = "Original (desconectado)"
    else:
        c.default_value = tuple(mat.diffuse_color)

    for link in list(out.inputs["Surface"].links):
        L.remove(link)
    L.new(g.outputs["Shader"], out.inputs["Surface"])
    return True


# ------------------------------------------------------------------
# 3. Contorno (inverted hull)
# ------------------------------------------------------------------
def material_contorno():
    mat = bpy.data.materials.get(MAT_CONTORNO) or bpy.data.materials.new(MAT_CONTORNO)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    N, L = mat.node_tree.nodes, mat.node_tree.links
    N.clear()
    out = nd(N, "ShaderNodeOutputMaterial", 500, 0)
    emi = nd(N, "ShaderNodeEmission", 0, 120)
    emi.inputs["Color"].default_value = lin(COLOR_CONTORNO)
    trans = nd(N, "ShaderNodeBsdfTransparent", 0, -60)
    geo = nd(N, "ShaderNodeNewGeometry", -400, 200)
    lp = nd(N, "ShaderNodeLightPath", -400, -100)
    fac = math_node(N, L, -150, 100, "MAXIMUM", geo.outputs["Backfacing"],
                    lp.outputs["Is Shadow Ray"])
    mix = nd(N, "ShaderNodeMixShader", 250, 0)
    L.new(fac, mix.inputs[0])
    L.new(emi.outputs["Emission"], mix.inputs[1])
    L.new(trans.outputs["BSDF"], mix.inputs[2])
    L.new(mix.outputs["Shader"], out.inputs["Surface"])
    mat.diffuse_color = lin(COLOR_CONTORNO)
    mat.use_backface_culling = True
    for attr, val in (("use_transparent_shadow", True), ("shadow_method", "NONE"),
                      ("use_backface_culling_shadow", True)):
        try:
            setattr(mat, attr, val)
        except Exception:
            pass
    return mat


def poner_contorno(obj, mat_out, grosor_mundo):
    data = obj.data
    if data is None or not hasattr(data, "materials"):
        return False
    reales = [m for m in data.materials if m is not None and m != mat_out]
    if not reales:
        return False                     # sin material: se dejaría todo negro

    mod = obj.modifiers.get(MOD_CONTORNO)
    if mod is None:
        try:
            mod = obj.modifiers.new(MOD_CONTORNO, "SOLIDIFY")
        except Exception:
            return False
    if mat_out.name not in [m.name for m in data.materials if m]:
        data.materials.append(mat_out)
    idx = [i for i, m in enumerate(data.materials) if m == mat_out][0]
    esc = obj.matrix_world.to_scale()
    s = (abs(esc.x) + abs(esc.y) + abs(esc.z)) / 3.0 or 1.0
    mod.thickness = grosor_mundo / s
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.use_even_offset = True
    mod.use_quality_normals = True
    mod.material_offset = idx            # el casco usa el último hueco (contorno)
    mod.material_offset_rim = idx
    mod.show_in_editmode = False
    return True


# ------------------------------------------------------------------
# 4. Cielo de atardecer
# ------------------------------------------------------------------
def construir_cielo(scene):
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    N, L = world.node_tree.nodes, world.node_tree.links
    N.clear()

    out = nd(N, "ShaderNodeOutputWorld", 2600, 0)
    tc = nd(N, "ShaderNodeTexCoord", -1800, 0)
    rot = nd(N, "ShaderNodeMapping", -1600, 0, "Girar cielo (Z)")
    rot.vector_type = "VECTOR"
    rot.inputs["Rotation"].default_value = (0, 0, math.radians(GIRO_CIELO))
    L.new(tc.outputs["Generated"], rot.inputs["Vector"])
    nrm = nd(N, "ShaderNodeVectorMath", -1400, 0)
    nrm.operation = "NORMALIZE"
    L.new(rot.outputs["Vector"], nrm.inputs[0])
    d = nrm.outputs["Vector"]
    sep = nd(N, "ShaderNodeSeparateXYZ", -1200, 200)
    L.new(d, sep.inputs["Vector"])
    z = sep.outputs["Z"]

    # --- Degradado del cielo (altura del horizonte -> cenit)
    def zpos(zz):
        return (zz + 0.2) / 1.2
    t = map_range(N, L, -1000, 400, z, -0.2, 1.0)
    grad = ramp(N, -800, 400, [
        (zpos(-0.20), lin("#1c0f2e")),
        (zpos(-0.02), lin("#3a1a40")),
        (zpos(0.00), lin("#ffcf7a")),
        (zpos(0.04), lin("#ff9f45")),
        (zpos(0.12), lin("#ff6a55")),
        (zpos(0.25), lin("#d44a7a")),
        (zpos(0.45), lin("#7a3488")),
        (zpos(0.70), lin("#33236a")),
        (zpos(1.00), lin("#15123a")),
    ], interp="LINEAR", label="Colores del cielo")
    L.new(t, grad.inputs["Fac"])
    cielo = grad.outputs["Color"]

    # --- Sol pintado
    az, el = math.radians(SOL_CIELO_AZIMUT), math.radians(SOL_CIELO_ELEVACION)
    sdir = nd(N, "ShaderNodeCombineXYZ", -1200, -300, "Dirección del sol")
    sdir.inputs["X"].default_value = math.sin(az) * math.cos(el)
    sdir.inputs["Y"].default_value = math.cos(az) * math.cos(el)
    sdir.inputs["Z"].default_value = math.sin(el)
    dot = nd(N, "ShaderNodeVectorMath", -1000, -200)
    dot.operation = "DOT_PRODUCT"
    L.new(d, dot.inputs[0])
    L.new(sdir.outputs["Vector"], dot.inputs[1])
    cerca = dot.outputs["Value"]

    horizonte = map_range(N, L, -1000, -500, z, -0.004, 0.004, label="Corte del horizonte")

    # resplandor suave alrededor del sol
    glow = map_range(N, L, -800, -100, cerca, 0.70, 1.0, interp="SMOOTHSTEP")
    glow = math_node(N, L, -600, -100, "POWER", glow, 2.5)
    glow = math_node(N, L, -420, -100, "MULTIPLY", glow, 0.55)
    bajo = map_range(N, L, -600, -200, z, -0.03, 0.01)
    glow = math_node(N, L, -420, -200, "MULTIPLY", glow, bajo)
    _, cielo = mix_color(N, L, -200, 300, "SCREEN", glow, cielo, lin("#ffb066"), "Resplandor")

    # halos por bandas + disco del sol
    tsol = map_range(N, L, -800, -300, cerca, 0.97, 1.0)
    halos = ramp(N, -600, -300, [
        (0.0, (0, 0, 0, 0)),
        (0.50, lin("#ffb35c", 0.18)),
        (0.75, lin("#ffc879", 0.38)),
        (0.938, lin("#fff4d6", 1.0)),     # disco del sol (~3.5°)
    ], label="Sol y halos")
    L.new(tsol, halos.inputs["Fac"])
    a_sol = math_node(N, L, -300, -380, "MULTIPLY", halos.outputs["Alpha"], horizonte)
    _, cielo = mix_color(N, L, 0, 250, "MIX", a_sol, cielo, halos.outputs["Color"], "Sol")

    # --- Nubes cartoon de dos tonos
    if NUBES:
        zc = math_node(N, L, -1000, -800, "MAXIMUM", z, 0.02)
        zv = nd(N, "ShaderNodeCombineXYZ", -820, -800)
        for k in ("X", "Y", "Z"):
            L.new(zc, zv.inputs[k])
        proj = nd(N, "ShaderNodeVectorMath", -640, -700)      # proyección a un plano de nubes
        proj.operation = "DIVIDE"
        L.new(d, proj.inputs[0])
        L.new(zv.outputs["Vector"], proj.inputs[1])
        ps = nd(N, "ShaderNodeSeparateXYZ", -460, -700)
        L.new(proj.outputs["Vector"], ps.inputs["Vector"])
        p2 = nd(N, "ShaderNodeCombineXYZ", -300, -700)
        L.new(ps.outputs["X"], p2.inputs["X"])
        L.new(ps.outputs["Y"], p2.inputs["Y"])
        radial = nd(N, "ShaderNodeVectorMath", -140, -820)
        radial.operation = "NORMALIZE"
        L.new(p2.outputs["Vector"], radial.inputs[0])
        desp = nd(N, "ShaderNodeVectorMath", 20, -820)
        desp.operation = "SCALE"
        L.new(radial.outputs["Vector"], desp.inputs[0])
        sock(desp.inputs, "Scale", "VALUE").default_value = 0.12
        p_abajo = nd(N, "ShaderNodeVectorMath", 180, -820)
        p_abajo.operation = "ADD"
        L.new(p2.outputs["Vector"], p_abajo.inputs[0])
        L.new(desp.outputs["Vector"], p_abajo.inputs[1])

        def ruido(vec, y):
            m = nd(N, "ShaderNodeMapping", 360, y, "Forma de nubes")
            m.vector_type = "POINT"
            m.inputs["Location"].default_value = (3.7, 1.3, 0.0)
            m.inputs["Scale"].default_value = (0.3, 0.75, 1.0)
            L.new(vec, m.inputs["Vector"])
            n = nd(N, "ShaderNodeTexNoise", 560, y)
            n.noise_dimensions = "2D"
            n.inputs["Scale"].default_value = 1.0
            n.inputs["Detail"].default_value = 2.0
            n.inputs["Roughness"].default_value = 0.5
            L.new(m.outputs["Vector"], n.inputs["Vector"])
            return n.outputs["Fac"]

        UMBRAL_NUBE = 0.56
        c1 = math_node(N, L, 760, -650, "GREATER_THAN", ruido(p2.outputs["Vector"], -650),
                       UMBRAL_NUBE, label="Cantidad de nubes")
        c2 = math_node(N, L, 760, -900, "GREATER_THAN", ruido(p_abajo.outputs["Vector"], -900),
                       UMBRAL_NUBE)
        filo = math_node(N, L, 940, -800, "SUBTRACT", c1, c2, clamp=True)   # borde inferior iluminado

        f1 = map_range(N, L, 760, -1150, z, 0.05, 0.12)
        f2 = map_range(N, L, 760, -1350, z, 0.42, 0.22)
        fade = math_node(N, L, 940, -1250, "MULTIPLY", f1, f2)
        mascara = math_node(N, L, 1120, -900, "MULTIPLY", c1, fade)

        prox = map_range(N, L, 940, -450, cerca, 0.85, 0.99)
        _, cuerpo = mix_color(N, L, 1120, -350, "MIX", prox, lin("#8e3f80"), lin("#c45a7a"),
                              "Color nube")
        _, filo_col = mix_color(N, L, 1120, -550, "MIX", prox, lin("#ff9e7a"), lin("#ffe4a8"),
                                "Filo iluminado")
        _, nube = mix_color(N, L, 1320, -450, "MIX", filo, cuerpo, filo_col)
        _, cielo = mix_color(N, L, 1550, 150, "MIX", mascara, cielo, nube, "Nubes")

    # --- Fondo visible a cámara vs. luz ambiente tenue
    bg_cam = nd(N, "ShaderNodeBackground", 1900, 150, "Cielo visible")
    L.new(cielo, bg_cam.inputs["Color"])
    bg_cam.inputs["Strength"].default_value = 1.0
    bg_amb = nd(N, "ShaderNodeBackground", 1900, -100, "Luz ambiente")
    L.new(grad.outputs["Color"], bg_amb.inputs["Color"])
    bg_amb.inputs["Strength"].default_value = LUZ_AMBIENTE
    lp = nd(N, "ShaderNodeLightPath", 1900, 500)
    mix = nd(N, "ShaderNodeMixShader", 2300, 0)
    L.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    L.new(bg_amb.outputs["Background"], mix.inputs[1])
    L.new(bg_cam.outputs["Background"], mix.inputs[2])
    L.new(mix.outputs["Shader"], out.inputs["Surface"])
    world.color = lin("#ff9f45")[:3]
    return world


# ------------------------------------------------------------------
# 5. Luz, cámara y ajustes de render
# ------------------------------------------------------------------
def crear_sol(scene):
    sol = next((o for o in scene.objects if o.type == "LIGHT" and o.data.type == "SUN"), None)
    if sol is None:
        data = bpy.data.lights.new("Sol Atardecer", type="SUN")
        sol = bpy.data.objects.new("Sol Atardecer", data)
        scene.collection.objects.link(sol)
    luz = sol.data
    luz.energy = LUZ_FUERZA
    luz.color = lin(LUZ_COLOR)[:3]
    luz.angle = math.radians(1.0)
    luz.use_shadow = True
    az, el = math.radians(LUZ_AZIMUT), math.radians(LUZ_ELEVACION)
    hacia_luz = Vector((-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    sol.rotation_euler = hacia_luz.to_track_quat("Z", "Y").to_euler()
    sol.location = hacia_luz * 15 + Vector((0, 0, 4))
    return sol


def objetos_modelo(scene):
    mallas = [o for o in scene.objects if o.type in {"MESH", "CURVE"} and o.visible_get()]
    con_espejo = [o for o in mallas if any(m.type == "MIRROR" for m in o.modifiers)]
    return con_espejo or mallas


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


def crear_camara(scene, lo, hi):
    if scene.camera is not None or not CREAR_CAMARA:
        return None
    h = hi.z - lo.z
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    data = bpy.data.cameras.new("Camara Cartoon")
    data.lens = 35
    data.clip_end = max(1000.0, h * 50)
    cam = bpy.data.objects.new("Camara Cartoon", data)
    scene.collection.objects.link(cam)
    cam.location = Vector((cx, cy - 2.3 * h, lo.z + 0.2 * h))      # de frente, contrapicado
    mira = Vector((cx, cy, lo.z + 0.5 * h))
    cam.rotation_euler = (mira - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return cam


def ajustes_render(scene):
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = eng
            break
        except Exception:
            pass
    scene.render.film_transparent = False
    vs = scene.view_settings
    vs.view_transform = "Standard"      # Filmic/AgX lavan los colores
    vs.look = "None"
    vs.exposure = 0.0
    vs.gamma = 1.0
    try:
        scene.eevee.use_shadows = True
    except Exception:
        pass


def vista_renderizada():
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    for sp in area.spaces:
                        if sp.type == "VIEW_3D":
                            sp.shading.type = "RENDERED"
    except Exception:
        pass


# ------------------------------------------------------------------
# 0. Quitar lo que agregó la versión anterior del script
# ------------------------------------------------------------------
def limpiar_extras(scene):
    quitados = 0
    mat_out = bpy.data.materials.get(MAT_CONTORNO)
    for o in bpy.data.objects:
        mod = o.modifiers.get(MOD_CONTORNO) if hasattr(o, "modifiers") else None
        if mod is not None:
            o.modifiers.remove(mod)
            quitados += 1
        data = getattr(o, "data", None)
        if mat_out is not None and data is not None and hasattr(data, "materials"):
            for i in reversed(range(len(data.materials))):
                if data.materials[i] == mat_out:
                    data.materials.pop(index=i)
    if mat_out is not None:
        bpy.data.materials.remove(mat_out)

    if not CREAR_CAMARA:
        cam = bpy.data.objects.get("Camara Cartoon")
        if cam is not None:
            if scene.camera == cam:
                scene.camera = None
            cdata = cam.data
            bpy.data.objects.remove(cam)
            if cdata is not None and cdata.users == 0:
                bpy.data.cameras.remove(cdata)

    if not OCULTAR_ESFERAS_EN_RENDER:
        for o in scene.objects:
            if o.type == "MESH" and o.name.startswith("Sphere"):
                o.hide_render = False
    return quitados


def main():
    scene = bpy.context.scene
    quitados = limpiar_extras(scene)
    ng = construir_grupo()

    convertidos = []
    for mat in bpy.data.materials:
        if mat.name == MAT_CONTORNO or getattr(mat, "is_grease_pencil", False):
            continue
        if mat.library is not None:
            continue
        if convertir_material(mat, ng):
            convertidos.append(mat.name)

    modelo = objetos_modelo(scene)
    lo, hi = caja_mundo(modelo)
    tam = (hi - lo).length

    con_contorno = 0
    if CONTORNO:
        mat_out = material_contorno()
        for o in scene.objects:
            if o.type in {"MESH", "CURVE"} and poner_contorno(o, mat_out, GROSOR_CONTORNO * tam):
                con_contorno += 1

    construir_cielo(scene)
    crear_sol(scene)
    cam = crear_camara(scene, lo, hi)
    ajustes_render(scene)

    if OCULTAR_ESFERAS_EN_RENDER:
        for o in scene.objects:
            if o.type == "MESH" and o.name.startswith("Sphere") and o not in modelo:
                o.hide_render = True

    if not bpy.app.background:
        vista_renderizada()

    print("=" * 60)
    print("Estilo cartoon aplicado a:", ", ".join(convertidos))
    print("Contornos anteriores quitados:", quitados)
    print("Objetos con contorno:", con_contorno)
    print("Cámara creada:", cam.name if cam else "no (ya había una)")
    print("=" * 60)

    if bpy.app.background and bpy.data.filepath:
        destino = bpy.data.filepath[:-6] + "_cartoon.blend"
        bpy.ops.wm.save_as_mainfile(filepath=destino, copy=True)
        print("Guardado en:", destino)


main()
