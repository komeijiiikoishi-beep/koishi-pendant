"""
Build r5: Rollback r4 gradual push (caused oscillation), keep P1 high-speed pass-through.
         Instant clamp (correct for Verlet) + hard stop + sliding + pass-through.

Fixes from r4:
  - Restored ropeOldY guard (prevents multi-frame re-trigger → oscillation)
  - Restored instant position clamp (Verlet needs single-frame collision)
  - Changed elastic rebound (vy*0.3) to hard stop (ropeOldY = ropeY)
    → no false velocity, just clean collision
  - Kept |vy|>28 pass-through
  - Kept X untouched (sliding)

Previous patches: P1(DWM) P2(freeze) P3(screen+oldY_clamp) P4a(damping) P4b(rest) P4c(perturb)

Requires: Mono.Cecil, WinPlat.dll
Output: 恋恋挂件_r5.exe
"""
import clr, sys, os
sys.path.append(r"C:\Users\LENOVO\Downloads\mono.cecil\lib\net40")
clr.AddReference("Mono.Cecil")
from Mono.Cecil import *
from Mono.Cecil.Cil import *
from System import Int32 as SInt32
from System import Single as SSingle

BASE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(BASE, "恋恋挂件-本地测试版-v1.exe")
DLL  = os.path.join(BASE, "WinPlat.dll")
OUT  = os.path.join(BASE, "恋恋挂件_r5.exe")
OVERLAY_OFFSET = 581632

with open(ORIG, "rb") as f: overlay = f.read()[OVERLAY_OFFSET:]
asm = AssemblyDefinition.ReadAssembly(ORIG)
mod = asm.MainModule
PA = getattr(ParameterAttributes, "None")
form1 = next(t for t in mod.Types if t.Name == "Form1")

# ═══════════════════════════════════════════════════════════════
# P1: DWM shadow fix
# ═══════════════════════════════════════════════════════════════
wt = next(t for t in mod.Types if t.Name == "WpfPendantOverlayWindow")
ri = ByReferenceType(mod.TypeSystem.Int32)
dr = ModuleReference("dwmapi.dll"); mod.ModuleReferences.Add(dr)
dm = MethodDefinition("DwmSetWindowAttribute",
    MethodAttributes.PInvokeImpl | MethodAttributes.Static | MethodAttributes.Private,
    mod.TypeSystem.Int32)
for n, t in [("hwnd", mod.TypeSystem.IntPtr), ("dwAttribute", mod.TypeSystem.Int32),
              ("pvAttribute", ri), ("cbAttribute", mod.TypeSystem.Int32)]:
    dm.Parameters.Add(ParameterDefinition(n, PA, t))
dm.PInvokeInfo = PInvokeInfo(PInvokeAttributes.CallConvWinapi, "DwmSetWindowAttribute", dr)
dm.ImplAttributes = MethodImplAttributes.PreserveSig; wt.Methods.Add(dm)
for n, v in [("DWMWA_NCRENDERING_POLICY", 2), ("DWMNCRP_DISABLED", 1)]:
    f = FieldDefinition(n, FieldAttributes.Static | FieldAttributes.Private | FieldAttributes.Literal,
                        mod.TypeSystem.Int32)
    f.Constant = SInt32(v); wt.Fields.Add(f)
si_m = next(m for m in wt.Methods if m.Name == "WpfPendantOverlayWindow_SourceInitialized")
lv_v = VariableDefinition(mod.TypeSystem.Int32); si_m.Body.Variables.Add(lv_v)
il_s = si_m.Body.GetILProcessor()
for i in [il_s.Create(OpCodes.Ldloc_0), il_s.Create(OpCodes.Ldc_I4_2), il_s.Create(OpCodes.Ldc_I4_1),
          il_s.Create(OpCodes.Stloc, lv_v), il_s.Create(OpCodes.Ldloca, lv_v),
          il_s.Create(OpCodes.Ldc_I4_4), il_s.Create(OpCodes.Call, dm), il_s.Create(OpCodes.Pop)]:
    il_s.InsertBefore(next(x for x in si_m.Body.Instructions if x.OpCode == OpCodes.Ret), i)
print("P1: DWM shadow")

# ═══════════════════════════════════════════════════════════════
# P2: Cursor freeze
# ═══════════════════════════════════════════════════════════════
upf = next(m for m in form1.Methods if m.Name == "UpdatePendantFrame")
for ins in upf.Body.Instructions:
    if ins.OpCode == OpCodes.Call and "IsSystemCursorHidden" in str(ins.Operand):
        n = upf.Body.Instructions[upf.Body.Instructions.IndexOf(ins) + 1]
        if n.OpCode in (OpCodes.Brfalse, OpCodes.Brfalse_S):
            il_u = upf.Body.GetILProcessor(); il_u.InsertBefore(n, il_u.Create(OpCodes.Pop))
            n.OpCode = OpCodes.Br_S
        break
print("P2: cursor freeze")

# ═══════════════════════════════════════════════════════════════
# P4a: Damping tune
# ═══════════════════════════════════════════════════════════════
DAMPING_OLD = 0.996999979019165
DAMPING_NEW = 0.9984999895095825
damping_count = 0
for m in form1.Methods:
    if not m.HasBody: continue
    if m.Name in ("IntegratePhysicsEngine3Points", "GetPhysicsEngine3PendantDamping"):
        for ins in m.Body.Instructions:
            if ins.OpCode == OpCodes.Ldc_R4:
                val = float(ins.Operand)
                if abs(val - DAMPING_OLD) < 1e-8:
                    ins.Operand = SSingle(DAMPING_NEW)
                    damping_count += 1
print(f"P4a: damping 0.997→0.9985 ({damping_count} occurrences)")

# ═══════════════════════════════════════════════════════════════
# P4b: Rest delay
# ═══════════════════════════════════════════════════════════════
REST_OLD = 0.30000001192092896
REST_NEW = 0.800000011920929
rest_count = 0
for m in form1.Methods:
    if not m.HasBody: continue
    if "Engine3" not in m.Name: continue
    for ins in m.Body.Instructions:
        if ins.OpCode == OpCodes.Ldc_R4:
            val = float(ins.Operand)
            if abs(val - REST_OLD) < 1e-8:
                ins.Operand = SSingle(REST_NEW)
                rest_count += 1
print(f"P4b: rest delay 0.3→0.8s ({rest_count} occurrences)")

# ═══════════════════════════════════════════════════════════════
# P3 + P1: Screen edge clamp + Window collision with pass-through
# ==================================================================
# Design:
#   - Instant position clamp (correct for Verlet integration)
#   - ropeOldY guard prevents multi-frame re-trigger
#   - |vy|>28 → pass-through (high speed)
#   - ropeOldY = ropeY (hard stop, no elastic bounce)
#   - X untouched (sliding along surface)
# ═══════════════════════════════════════════════════════════════
dll = AssemblyDefinition.ReadAssembly(DLL)
mod.AssemblyReferences.Add(AssemblyNameReference(dll.Name.Name, dll.Name.Version))
wp_t = next(t for t in dll.MainModule.Types if t.Name == "WindowPlatforms")
M = lambda name: mod.ImportReference(next(m for m in wp_t.Methods if m.Name == name))
wp_update, wp_count = M("Update"), M("GetCount")
wp_top, wp_left, wp_right = M("GetTop"), M("GetLeft"), M("GetRight")

msr = next(r for r in mod.AssemblyReferences if r.Name == "mscorlib")
mtr = TypeReference("System", "Math", mod, msr).Resolve()
mmi = mod.ImportReference(next(m for m in mtr.Methods if m.Name == "Min" and m.Parameters.Count == 2 and m.Parameters[0].ParameterType.FullName == "System.Single"))
mma = mod.ImportReference(next(m for m in mtr.Methods if m.Name == "Max" and m.Parameters.Count == 2 and m.Parameters[0].ParameterType.FullName == "System.Single"))
msin = mod.ImportReference(next(m for m in mtr.Methods if m.Name == "Sin" and m.Parameters.Count == 1 and m.Parameters[0].ParameterType.FullName == "System.Double"))
mabs = mod.ImportReference(next(m for m in mtr.Methods if m.Name == "Abs" and m.Parameters.Count == 1 and m.Parameters[0].ParameterType.FullName == "System.Double"))

upe3 = next(m for m in form1.Methods if m.Name == "UpdatePhysicsEngine3")
vy_var = VariableDefinition(mod.TypeSystem.Single)
upe3.Body.Variables.Add(vy_var)
gsm = next(m for m in form1.Methods if m.Name == "GetSystemMetrics")
rxf, ryf, royf = [next(f for f in form1.Fields if f.Name == n) for n in ["ropeX", "ropeY", "ropeOldY"]]

after = None
for ins in upe3.Body.Instructions:
    if ins.OpCode == OpCodes.Call and "IntegratePhysicsEngine3Points" in str(ins.Operand):
        after = ins; break

il3 = upe3.Body.GetILProcessor()

def C(op, operand=None):
    return il3.Create(op, operand) if operand is not None else il3.Create(op)

S = []

# 1. WindowPlatforms.Update()
S.append((C(OpCodes.Call, wp_update), None))
S.append((C(OpCodes.Pop), None))

# 2. Screen edge clamp
S.extend([
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldelem_R4), None), (C(OpCodes.Ldc_I4_0), None), (C(OpCodes.Call, gsm), None),
    (C(OpCodes.Conv_R4), None), (C(OpCodes.Call, mmi), None), (C(OpCodes.Ldc_R4, 0.0), None),
    (C(OpCodes.Call, mma), None), (C(OpCodes.Stelem_R4), None),
])
S.extend([
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldelem_R4), None), (C(OpCodes.Ldc_I4_1), None), (C(OpCodes.Call, gsm), None),
    (C(OpCodes.Conv_R4), None), (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
    (C(OpCodes.Call, mmi), None), (C(OpCodes.Ldc_R4, 0.0), None), (C(OpCodes.Call, mma), None),
    (C(OpCodes.Stelem_R4), None),
])
S.extend([
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldelem_R4), None), (C(OpCodes.Ldc_I4_1), None), (C(OpCodes.Call, gsm), None),
    (C(OpCodes.Conv_R4), None), (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
    (C(OpCodes.Call, mmi), None), (C(OpCodes.Ldc_R4, 0.0), None), (C(OpCodes.Call, mma), None),
    (C(OpCodes.Stelem_R4), None),
])

# 3. Window platform collision: instant clamp + pass-through + hard stop
# Per platform:
#   if count <= pi → skip
#   if ropeOldY >= top → skip (already on platform, prevent re-trigger)
#   if ropeY+20 < top → skip (above platform)
#   if ropeX outside [left,right] → skip
#   vy = ropeY - ropeOldY
#   if |vy| > 28 → skip (high-speed pass-through)
#   ropeY = top - 20  (instant clamp)
#   ropeOldY = top - 20  (hard stop, no rebound velocity)
#   X untouched (sliding)
HIGH_SPEED = 28.0

for pi in range(4):
    plat_end = C(OpCodes.Nop)
    check = [
        (C(OpCodes.Call, wp_count), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None),
        (C(OpCodes.Ble, plat_end), None),

        # Guard: ropeOldY[idx] >= top → already on platform → skip
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Bge, plat_end), None),

        # ropeY[idx] + 20 >= top? (pendant bottom reaches platform)
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Add), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Blt, plat_end), None),

        # ropeX >= left?
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_left), None),
        (C(OpCodes.Blt, plat_end), None),

        # ropeX <= right?
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_right), None),
        (C(OpCodes.Bgt, plat_end), None),

        # vy = ropeY - ropeOldY
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Sub), None),
        (C(OpCodes.Stloc, vy_var), None),

        # High-speed pass-through: |vy| > 28 → skip
        (C(OpCodes.Ldloc, vy_var), None),
        (C(OpCodes.Conv_R8), None),
        (C(OpCodes.Call, mabs), None),
        (C(OpCodes.Conv_R4), None),
        (C(OpCodes.Ldc_R4, SSingle(HIGH_SPEED)), None),
        (C(OpCodes.Bgt, plat_end), None),

        # ropeY[idx] = GetTop(pi) - 20  (instant clamp)
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None),
        (C(OpCodes.Ldloc_0), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
        (C(OpCodes.Stelem_R4), None),

        # ropeOldY[idx] = GetTop(pi) - 20  (hard stop, no bounce)
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None),
        (C(OpCodes.Ldloc_0), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
        (C(OpCodes.Stelem_R4), None),

        (plat_end, None),
    ]
    S.extend(check)

for instr, _ in reversed(S):
    il3.InsertAfter(after, instr)

print(f"P3/P1: screen clamp + window collision + pass-through ({len(S)} IL)")
print(f"       |vy|>{HIGH_SPEED}→skip, instant clamp, hard stop, sliding X")

# ═══════════════════════════════════════════════════════════════
# P4c: Micro-perturbation
# ═══════════════════════════════════════════════════════════════
phase_field = FieldDefinition("_frozenMicroPhase",
    FieldAttributes.Static | FieldAttributes.Private,
    mod.TypeSystem.Int32)
form1.Fields.Add(phase_field)

freeze_m = next(m for m in form1.Methods if m.Name == "FreezePhysicsEngine3AtRest")
freeze_il = freeze_m.Body.GetILProcessor()
freeze_ret = next(x for x in freeze_m.Body.Instructions if x.OpCode == OpCodes.Ret)

ox_var = VariableDefinition(mod.TypeSystem.Single)
oy_var = VariableDefinition(mod.TypeSystem.Single)
freeze_m.Body.Variables.Add(ox_var)
freeze_m.Body.Variables.Add(oy_var)

perturb = []

perturb.append(freeze_il.Create(OpCodes.Ldsfld, phase_field))
perturb.append(freeze_il.Create(OpCodes.Ldc_I4_1))
perturb.append(freeze_il.Create(OpCodes.Add))
perturb.append(freeze_il.Create(OpCodes.Dup))
perturb.append(freeze_il.Create(OpCodes.Stsfld, phase_field))
perturb.append(freeze_il.Create(OpCodes.Conv_R4))

# ox = sin(f*0.018)*1.0 + sin(f*0.102+1.7)*0.3
perturb.append(freeze_il.Create(OpCodes.Dup))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.018))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Conv_R8))
perturb.append(freeze_il.Create(OpCodes.Call, msin))
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 1.0))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Stloc, ox_var))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.102))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 1.7))
perturb.append(freeze_il.Create(OpCodes.Add))
perturb.append(freeze_il.Create(OpCodes.Conv_R8))
perturb.append(freeze_il.Create(OpCodes.Call, msin))
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.3))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Ldloc, ox_var))
perturb.append(freeze_il.Create(OpCodes.Add))
perturb.append(freeze_il.Create(OpCodes.Stloc, ox_var))

# oy = sin(f*0.022+0.7)*0.7 + sin(f*0.095)*0.2
perturb.append(freeze_il.Create(OpCodes.Ldsfld, phase_field))
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Dup))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.022))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.7))
perturb.append(freeze_il.Create(OpCodes.Add))
perturb.append(freeze_il.Create(OpCodes.Conv_R8))
perturb.append(freeze_il.Create(OpCodes.Call, msin))
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.7))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Stloc, oy_var))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.095))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Conv_R8))
perturb.append(freeze_il.Create(OpCodes.Call, msin))
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.2))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Ldloc, oy_var))
perturb.append(freeze_il.Create(OpCodes.Add))
perturb.append(freeze_il.Create(OpCodes.Stloc, oy_var))

# ropeX[idx] += ox
perturb.append(freeze_il.Create(OpCodes.Ldarg_0))
perturb.append(freeze_il.Create(OpCodes.Ldfld, rxf))
perturb.append(freeze_il.Create(OpCodes.Ldarg_1))
perturb.append(freeze_il.Create(OpCodes.Ldarg_0))
perturb.append(freeze_il.Create(OpCodes.Ldfld, rxf))
perturb.append(freeze_il.Create(OpCodes.Ldarg_1))
perturb.append(freeze_il.Create(OpCodes.Ldelem_R4))
perturb.append(freeze_il.Create(OpCodes.Ldloc, ox_var))
perturb.append(freeze_il.Create(OpCodes.Add))
perturb.append(freeze_il.Create(OpCodes.Stelem_R4))

# ropeY[idx] += oy
perturb.append(freeze_il.Create(OpCodes.Ldarg_0))
perturb.append(freeze_il.Create(OpCodes.Ldfld, ryf))
perturb.append(freeze_il.Create(OpCodes.Ldarg_1))
perturb.append(freeze_il.Create(OpCodes.Ldarg_0))
perturb.append(freeze_il.Create(OpCodes.Ldfld, ryf))
perturb.append(freeze_il.Create(OpCodes.Ldarg_1))
perturb.append(freeze_il.Create(OpCodes.Ldelem_R4))
perturb.append(freeze_il.Create(OpCodes.Ldloc, oy_var))
perturb.append(freeze_il.Create(OpCodes.Add))
perturb.append(freeze_il.Create(OpCodes.Stelem_R4))

for i in reversed(perturb):
    freeze_il.InsertBefore(freeze_ret, i)

print(f"P4c: micro-perturbation ({len(perturb)} IL)")

# ═══════════════════════════════════════════════════════════════
# Write
# ═══════════════════════════════════════════════════════════════
T = os.path.join(BASE, "_t.exe")
asm.Write(T)
with open(T, "rb") as f: pe = f.read()
with open(OUT, "wb") as f: f.write(pe + overlay)
os.remove(T)
print(f"\nDone: {OUT}")
print("Patches: P1(DWM) P2(freeze) P3(screen+clamp) P1(high-speed pass-through) P4a(damping) P4b(rest) P4c(perturb)")
print("Requires: WinPlat.dll next to exe")
