"""
Build: P1(DWM) + P2(freeze) + P3(taskbar collision) + P4a(damping 0.997→0.998)
      + P4b(rest delay 0.3→0.8s) + P4c(micro-perturbation when frozen)

Requires: Mono.Cecil, WinPlat.dll (compiled from updated WindowPlatforms.cs)
Output: 恋恋挂件_r1.exe
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
OUT  = os.path.join(BASE, "恋恋挂件_r1.exe")
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
# P4a: Damping tune — 0.997f → 0.9985f (IEEE 754: ~0.9984999895095825)
# Actual inlined value is 0.996999979019165 (0.997f), NOT the const 0.993
# RUNS BEFORE P3 to avoid matching P3's injected 0.3f restitution values
# ═══════════════════════════════════════════════════════════════
DAMPING_OLD = 0.996999979019165   # 0.997f
DAMPING_NEW = 0.9984999895095825  # 0.9985f

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
                    print(f"  Damping: {m.Name} @ IL_{ins.Offset:04X}, {val:.6f} → {DAMPING_NEW:.6f}")

print(f"P4a: damping 0.997→0.9985 ({damping_count} occurrences)")

# ═══════════════════════════════════════════════════════════════
# P4b: Rest delay — 0.3s → 0.8s
# RUNS BEFORE P3 to avoid matching P3's injected 0.3f restitution values
# ═══════════════════════════════════════════════════════════════
REST_OLD = 0.30000001192092896   # 0.3f
REST_NEW = 0.800000011920929     # 0.8f

rest_count = 0
for m in form1.Methods:
    if not m.HasBody: continue
    # Only Engine3 methods — Engine2's 0.3 is a different parameter
    if "Engine3" not in m.Name: continue
    for ins in m.Body.Instructions:
        if ins.OpCode == OpCodes.Ldc_R4:
            val = float(ins.Operand)
            if abs(val - REST_OLD) < 1e-8:
                ins.Operand = SSingle(REST_NEW)
                rest_count += 1
                print(f"  RestDelay: {m.Name} @ IL_{ins.Offset:04X}, {val:.6f} → {REST_NEW:.6f}")

print(f"P4b: rest delay 0.3→0.8s ({rest_count} occurrences)")

# ═══════════════════════════════════════════════════════════════
# P3: Screen edge clamp + WinPlat window collision
# (P4a/P4b must run before P3 to avoid matching injected 0.3f restitution)
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

upe3 = next(m for m in form1.Methods if m.Name == "UpdatePhysicsEngine3")
vy_var = VariableDefinition(mod.TypeSystem.Single)
upe3.Body.Variables.Add(vy_var)
gsm = next(m for m in form1.Methods if m.Name == "GetSystemMetrics")
rxf, ryf, royf = [next(f for f in form1.Fields if f.Name == n) for n in ["ropeX", "ropeY", "ropeOldY"]]

# Find insertion point: after IntegratePhysicsEngine3Points call
after = None
for ins in upe3.Body.Instructions:
    if ins.OpCode == OpCodes.Call and "IntegratePhysicsEngine3Points" in str(ins.Operand):
        after = ins; break

il3 = upe3.Body.GetILProcessor()

def C(op, operand=None):
    return il3.Create(op, operand) if operand is not None else il3.Create(op)

S = []  # instruction sequence

# 1. WindowPlatforms.Update() — must pop bool
S.append((C(OpCodes.Call, wp_update), None))
S.append((C(OpCodes.Pop), None))

# 2. Screen edge clamp
S.extend([
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldelem_R4), None), (C(OpCodes.Ldc_I4_0), None), (C(OpCodes.Call, gsm), None),
    (C(OpCodes.Conv_R4), None), (C(OpCodes.Call, mmi), None), (C(OpCodes.Ldc_R4, 0.0), None),
    (C(OpCodes.Call, mma), None), (C(OpCodes.Stelem_R4), None),
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None), (C(OpCodes.Ldloc_0), None),
    (C(OpCodes.Ldelem_R4), None), (C(OpCodes.Ldc_I4_1), None), (C(OpCodes.Call, gsm), None),
    (C(OpCodes.Conv_R4), None), (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
    (C(OpCodes.Call, mmi), None), (C(OpCodes.Ldc_R4, 0.0), None), (C(OpCodes.Call, mma), None),
    (C(OpCodes.Stelem_R4), None),
])

# 3. Window platform checks (4 platforms, unrolled)
for pi in range(4):
    plat_end = C(OpCodes.Nop)
    check = [
        (C(OpCodes.Call, wp_count), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None),
        (C(OpCodes.Ble, plat_end), None),

        # Guard: if ropeOldY[idx] >= GetTop(pi) → pendant already below platform → skip
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Bge, plat_end), None),

        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Add), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Blt, plat_end), None),

        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_left), None),
        (C(OpCodes.Blt, plat_end), None),

        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_right), None),
        (C(OpCodes.Bgt, plat_end), None),

        # Elastic collision: vy = ropeY[idx] - ropeOldY[idx]
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Sub), None),
        (C(OpCodes.Stloc, vy_var), None),
        # ropeY[idx] = GetTop(pi) - 20
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None),
        (C(OpCodes.Ldloc_0), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
        (C(OpCodes.Stelem_R4), None),
        # ropeOldY[idx] = (GetTop(pi)-20) + vy * 0.3  (elastic rebound)
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None),
        (C(OpCodes.Ldloc_0), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
        (C(OpCodes.Ldloc, vy_var), None),
        (C(OpCodes.Ldc_R4, 0.3), None), (C(OpCodes.Mul), None),
        (C(OpCodes.Add), None),
        (C(OpCodes.Stelem_R4), None),

        (plat_end, None),
    ]
    S.extend(check)

for instr, _ in reversed(S):
    il3.InsertAfter(after, instr)

print(f"P3: screen + {len(S)} IL (WinPlat.dll with taskbar)")

# ═══════════════════════════════════════════════════════════════
# P4c: Micro-perturbation when frozen
# Add static int field _frozenMicroPhase, inject sawtooth perturbation
# in FreezePhysicsEngine3AtRest (after the freeze loop, before ret)
# ═══════════════════════════════════════════════════════════════
# Add field
phase_field = FieldDefinition("_frozenMicroPhase",
    FieldAttributes.Static | FieldAttributes.Private,
    mod.TypeSystem.Int32)
form1.Fields.Add(phase_field)

# Locate FreezePhysicsEngine3AtRest
freeze_m = next(m for m in form1.Methods if m.Name == "FreezePhysicsEngine3AtRest")
freeze_il = freeze_m.Body.GetILProcessor()
freeze_ret = next(x for x in freeze_m.Body.Instructions if x.OpCode == OpCodes.Ret)

# Build perturbation IL (insert before ret):
# Dual-frequency sine: ox = sin(t*f1)*a1 + sin(t*f2+φ)*a2
#   f1=0.018 (0.29Hz breathing), a1=1.0px
#   f2=0.102 (1.62Hz micro-tremor), a2=0.3px
#   oy = same freqs with phase offsets + smaller amplitudes
# ropeX[pendantIndex] += ox;
# ropeY[pendantIndex] += oy;

perturb = []

# Add two float locals to the method body
ox_var = VariableDefinition(mod.TypeSystem.Single)
oy_var = VariableDefinition(mod.TypeSystem.Single)
freeze_m.Body.Variables.Add(ox_var)
freeze_m.Body.Variables.Add(oy_var)

# --- Block 1: Compute ox = sin(phase*0.018)*1.0 + sin(phase*0.102+1.7)*0.3 ---
# Increment phase
perturb.append(freeze_il.Create(OpCodes.Ldsfld, phase_field))   # [phase]
perturb.append(freeze_il.Create(OpCodes.Ldc_I4_1))
perturb.append(freeze_il.Create(OpCodes.Add))                    # [phase+1]
perturb.append(freeze_il.Create(OpCodes.Dup))                    # [newP, newP]
perturb.append(freeze_il.Create(OpCodes.Stsfld, phase_field))    # [newP]
perturb.append(freeze_il.Create(OpCodes.Conv_R4))                # [(float)newP]
# sin(phase * 0.018)
perturb.append(freeze_il.Create(OpCodes.Dup))                    # [f, f]
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.018))          # [f, f, 0.018]
perturb.append(freeze_il.Create(OpCodes.Mul))                    # [f, f*0.018]
perturb.append(freeze_il.Create(OpCodes.Conv_R8))                # [f, (double)]
perturb.append(freeze_il.Create(OpCodes.Call, msin))             # [f, sin(f*0.018)]
perturb.append(freeze_il.Create(OpCodes.Conv_R4))                # [f, (float)sin]
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 1.0))            # [f, sin, 1.0]
perturb.append(freeze_il.Create(OpCodes.Mul))                    # [f, sin*1.0]
# sin(phase * 0.102 + 1.7) * 0.3
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.102))          # [f, sin1, 0.102]
perturb.append(freeze_il.Create(OpCodes.Mul))                    # [f, sin1, f*0.102]
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 1.7))            # [f, sin1, f*0.102, 1.7]
perturb.append(freeze_il.Create(OpCodes.Add))                    # [f, sin1, f*0.102+1.7]
perturb.append(freeze_il.Create(OpCodes.Conv_R8))
perturb.append(freeze_il.Create(OpCodes.Call, msin))             # [f, sin1, sin(f*0.102+1.7)]
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.3))
perturb.append(freeze_il.Create(OpCodes.Mul))                    # [f, sin1, sin2*0.3]
perturb.append(freeze_il.Create(OpCodes.Add))                    # [f, sin1+sin2*0.3]
perturb.append(freeze_il.Create(OpCodes.Stloc, ox_var))          # store ox; stack: [f]

# --- Block 2: Compute oy = sin(phase*0.022+0.7)*0.7 + sin(phase*0.095)*0.2 ---
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.022))          # [f, 0.022]
perturb.append(freeze_il.Create(OpCodes.Mul))                    # [f*0.022]
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.7))            # [f*0.022, 0.7]
perturb.append(freeze_il.Create(OpCodes.Add))                    # [f*0.022+0.7]
perturb.append(freeze_il.Create(OpCodes.Conv_R8))
perturb.append(freeze_il.Create(OpCodes.Call, msin))             # [sin1]
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.7))            # amplitude
perturb.append(freeze_il.Create(OpCodes.Mul))                    # [sin1*0.7]
# sin(phase * 0.095) * 0.2
perturb.append(freeze_il.Create(OpCodes.Ldsfld, phase_field))    # [sin1*0.7, phase]
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.095))
perturb.append(freeze_il.Create(OpCodes.Mul))
perturb.append(freeze_il.Create(OpCodes.Conv_R8))
perturb.append(freeze_il.Create(OpCodes.Call, msin))
perturb.append(freeze_il.Create(OpCodes.Conv_R4))
perturb.append(freeze_il.Create(OpCodes.Ldc_R4, 0.2))
perturb.append(freeze_il.Create(OpCodes.Mul))                    # [sin1*0.7, sin2*0.2]
perturb.append(freeze_il.Create(OpCodes.Add))                    # [oy]
perturb.append(freeze_il.Create(OpCodes.Stloc, oy_var))          # store oy

# --- Block 3: ropeX[pendantIndex] += ox ---
perturb.append(freeze_il.Create(OpCodes.Ldarg_0))                # [this]
perturb.append(freeze_il.Create(OpCodes.Ldfld, rxf))             # [ropeX[]]
perturb.append(freeze_il.Create(OpCodes.Ldarg_1))                # [ropeX[], idx]
perturb.append(freeze_il.Create(OpCodes.Ldarg_0))                # [ropeX[], idx, this]
perturb.append(freeze_il.Create(OpCodes.Ldfld, rxf))             # [ropeX[], idx, ropeX[]]
perturb.append(freeze_il.Create(OpCodes.Ldarg_1))                # [ropeX[], idx, ropeX[], idx]
perturb.append(freeze_il.Create(OpCodes.Ldelem_R4))              # [ropeX[], idx, curX]
perturb.append(freeze_il.Create(OpCodes.Ldloc, ox_var))          # [ropeX[], idx, curX, ox]
perturb.append(freeze_il.Create(OpCodes.Add))                    # [ropeX[], idx, newX]
perturb.append(freeze_il.Create(OpCodes.Stelem_R4))              # []

# --- Block 4: ropeY[pendantIndex] += oy ---
perturb.append(freeze_il.Create(OpCodes.Ldarg_0))                # [this]
perturb.append(freeze_il.Create(OpCodes.Ldfld, ryf))             # [ropeY[]]
perturb.append(freeze_il.Create(OpCodes.Ldarg_1))                # [ropeY[], idx]
perturb.append(freeze_il.Create(OpCodes.Ldarg_0))                # [ropeY[], idx, this]
perturb.append(freeze_il.Create(OpCodes.Ldfld, ryf))             # [ropeY[], idx, ropeY[]]
perturb.append(freeze_il.Create(OpCodes.Ldarg_1))                # [ropeY[], idx, ropeY[], idx]
perturb.append(freeze_il.Create(OpCodes.Ldelem_R4))              # [ropeY[], idx, curY]
perturb.append(freeze_il.Create(OpCodes.Ldloc, oy_var))          # [ropeY[], idx, curY, oy]
perturb.append(freeze_il.Create(OpCodes.Add))                    # [ropeY[], idx, newY]
perturb.append(freeze_il.Create(OpCodes.Stelem_R4))              # []

# Insert all instructions before ret, in reverse order for correct sequence
for i in reversed(perturb):
    freeze_il.InsertBefore(freeze_ret, i)

print(f"P4c: dual-sine micro-perturbation ({len(perturb)} IL, sin(t*0.018)*1.0+sin(t*0.102+1.7)*0.3)")

# ═══════════════════════════════════════════════════════════════
# Write output
# ═══════════════════════════════════════════════════════════════
T = os.path.join(BASE, "_t.exe")
asm.Write(T)
with open(T, "rb") as f: pe = f.read()
with open(OUT, "wb") as f: f.write(pe + overlay)
os.remove(T)
print(f"\nDone: {OUT}")
print("Patches: P1(DWM) P2(freeze) P3(taskbar+screen) P4a(damping) P4b(rest) P4c(micro-perturb)")
print("Requires: WinPlat.dll next to exe")
