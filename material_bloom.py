# =====================================================================
#  MATERIAL BRILLANTE (BLOOM)  —  Blender 5.1+ (EEVEE)
#
#  1. Selecciona los objetos que quieres que brillen (opcional).
#  2. Scripting > Abrir > este archivo > ▶ Ejecutar.
#  Crea el material "Brillo Bloom" (emisión HDR con núcleo blanco) y un
#  compositor con Glare tipo Bloom.  En 5.x EEVEE ya no tiene casilla de
#  bloom: el halo se hace en el compositor (también se activa en el visor).
# =====================================================================
import bpy

COLOR = "#7dffb0"          # color del brillo
FUERZA = 5.0               # intensidad de la emisión (>1 para que brille)
NUCLEO = 0.5               # 0 = sin centro blanco, 1 = centro muy blanco
ASIGNAR_A_SELECCION = True # pone el material en los objetos seleccionados

UMBRAL_GLARE = 1.2         # solo brilla lo que supera este valor
TAMANO_GLARE = 0.75        # 0..1, tamaño del halo
FUERZA_GLARE = 0.9

MAT = "Brillo Bloom"
COMPOSITOR = "Compositor Bloom"


def lin(hexstr):
    h = hexstr.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (1.0,)


def material_bloom():
    mat = bpy.data.materials.get(MAT) or bpy.data.materials.new(MAT)
    if mat.node_tree is None:
        mat.use_nodes = True                     # solo en versiones viejas
    N, L = mat.node_tree.nodes, mat.node_tree.links
    N.clear()

    out = N.new("ShaderNodeOutputMaterial"); out.location = (700, 0)
    lw = N.new("ShaderNodeLayerWeight"); lw.location = (-700, 200)
    lw.inputs["Blend"].default_value = 0.5

    # centro de la cara a cámara = núcleo blanco; bordes = color saturado
    inv = N.new("ShaderNodeMath"); inv.location = (-500, 200)
    inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    L.new(lw.outputs["Facing"], inv.inputs[1])
    pw = N.new("ShaderNodeMath"); pw.location = (-320, 200)
    pw.operation = "POWER"; pw.inputs[1].default_value = 2.0
    L.new(inv.outputs[0], pw.inputs[0])
    k = N.new("ShaderNodeMath"); k.location = (-140, 200)
    k.operation = "MULTIPLY"; k.inputs[1].default_value = NUCLEO
    L.new(pw.outputs[0], k.inputs[0])

    mix = N.new("ShaderNodeMix"); mix.location = (60, 150)
    mix.data_type = "RGBA"; mix.label = "Núcleo blanco"
    L.new(k.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = lin(COLOR)            # A (color)
    mix.inputs[7].default_value = (1.0, 1.0, 1.0, 1.0)  # B (blanco)

    # pequeña variación de intensidad para que no se vea plano
    tc = N.new("ShaderNodeTexCoord"); tc.location = (-700, -200)
    nz = N.new("ShaderNodeTexNoise"); nz.location = (-500, -200)
    nz.inputs["Scale"].default_value = 4.0
    nz.inputs["Detail"].default_value = 1.0
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = N.new("ShaderNodeMapRange"); mr.location = (-300, -200)
    mr.label = "Intensidad (sube/baja el bloom)"
    mr.inputs["To Min"].default_value = FUERZA * 0.8
    mr.inputs["To Max"].default_value = FUERZA * 1.2
    L.new(nz.outputs["Fac"], mr.inputs["Value"])

    emi = N.new("ShaderNodeEmission"); emi.location = (400, 0)
    L.new(mix.outputs[2], emi.inputs["Color"])           # Result (color)
    L.new(mr.outputs["Result"], emi.inputs["Strength"])
    L.new(emi.outputs["Emission"], out.inputs["Surface"])
    mat.diffuse_color = lin(COLOR)
    return mat


def opcion(node, intentos):
    """Entre versiones, las opciones del Glare pasaron de propiedad a socket."""
    for donde, nombre, valores in intentos:
        for v in (valores if isinstance(valores, list) else [valores]):
            try:
                if donde == "socket":
                    s = node.inputs.get(nombre)
                    if s is None:
                        break
                    s.default_value = v
                else:
                    if not hasattr(node, nombre):
                        break
                    setattr(node, nombre, v)
                return
            except Exception:
                continue


def compositor_bloom(scene):
    if hasattr(scene, "compositing_node_group"):          # Blender 5.0+
        tree = bpy.data.node_groups.get(COMPOSITOR) or \
            bpy.data.node_groups.new(COMPOSITOR, "CompositorNodeTree")
        scene.compositing_node_group = tree
        tree.interface.clear()
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        nuevo = True
    else:
        scene.use_nodes = True
        tree = scene.node_tree
        nuevo = False
    N, L = tree.nodes, tree.links
    N.clear()

    rl = N.new("CompositorNodeRLayers"); rl.location = (-400, 0)
    gl = N.new("CompositorNodeGlare"); gl.location = (0, 0); gl.label = "Bloom"
    opcion(gl, [("socket", "Type", ["BLOOM", "Bloom"]), ("prop", "glare_type", "BLOOM")])
    opcion(gl, [("socket", "Quality", ["HIGH", "High"]), ("prop", "quality", "HIGH")])
    opcion(gl, [("socket", "Threshold", UMBRAL_GLARE), ("prop", "threshold", UMBRAL_GLARE)])
    opcion(gl, [("socket", "Strength", FUERZA_GLARE), ("prop", "mix", FUERZA_GLARE - 1.0)])
    opcion(gl, [("socket", "Size", TAMANO_GLARE),
                ("prop", "size", max(1, min(9, round(TAMANO_GLARE * 9))))])
    L.new(rl.outputs["Image"], gl.inputs["Image"])

    if nuevo:
        fin = N.new("NodeGroupOutput")
    else:
        fin = N.new("CompositorNodeComposite")
    fin.location = (300, 0)
    L.new(gl.outputs["Image"], fin.inputs["Image"])
    viewer = N.new("CompositorNodeViewer"); viewer.location = (300, -200)
    L.new(gl.outputs["Image"], viewer.inputs["Image"])


def main():
    scene = bpy.context.scene
    mat = material_bloom()
    asignados = []
    if ASIGNAR_A_SELECCION:
        for o in bpy.context.selected_objects:
            if o.type in {"MESH", "CURVE", "META"}:
                o.data.materials.clear()
                o.data.materials.append(mat)
                asignados.append(o.name)

    compositor_bloom(scene)
    scene.render.use_compositing = True
    for screen in bpy.data.screens:       # todos los espacios de trabajo (Layout, Shading...)
        for area in screen.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
                        sp.shading.use_compositor = "ALWAYS"
    print("Material:", mat.name, "| asignado a:", ", ".join(asignados) or "-")


main()
