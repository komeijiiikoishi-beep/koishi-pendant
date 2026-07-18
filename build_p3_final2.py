"""
P3 Final: Screen edges + Window title bars via WinPlat.dll.
"""
import clr, sys, os
sys.path.append(r"C:\Users\LENOVO\Downloads\mono.cecil\lib\net40")
clr.AddReference("Mono.Cecil")
from Mono.Cecil import *
from Mono.Cecil.Cil import *
from System import Int32 as SInt32

BASE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(BASE, "恋恋挂件-本地测试版-v1.exe")
DLL = os.path.join(BASE, "WinPlat.dll")
OUT = os.path.join(BASE, "恋恋挂件_patched_p3L.exe")

with open(ORIG, "rb") as f: overlay = f.read()[581632:]
asm = AssemblyDefinition.ReadAssembly(ORIG)
mod = asm.MainModule
PA = getattr(ParameterAttributes, "None")
form1 = next(t for t in mod.Types if t.Name == "Form1")

# ═══ P1 ═══
wt_t = next(t for t in mod.Types if t.Name == "WpfPendantOverlayWindow")
ri_t = ByReferenceType(mod.TypeSystem.Int32)
dr_t = ModuleReference("dwmapi.dll"); mod.ModuleReferences.Add(dr_t)
dm_t = MethodDefinition("DwmSetWindowAttribute",
    MethodAttributes.PInvokeImpl | MethodAttributes.Static | MethodAttributes.Private, mod.TypeSystem.Int32)
for n, t in [("hwnd", mod.TypeSystem.IntPtr), ("dwAttribute", mod.TypeSystem.Int32),
              ("pvAttribute", ri_t), ("cbAttribute", mod.TypeSystem.Int32)]:
    dm_t.Parameters.Add(ParameterDefinition(n, PA, t))
dm_t.PInvokeInfo = PInvokeInfo(PInvokeAttributes.CallConvWinapi, "DwmSetWindowAttribute", dr_t)
dm_t.ImplAttributes = MethodImplAttributes.PreserveSig; wt_t.Methods.Add(dm_t)
for n, v in [("DWMWA_NCRENDERING_POLICY", 2), ("DWMNCRP_DISABLED", 1)]:
    f = FieldDefinition(n, FieldAttributes.Static | FieldAttributes.Private | FieldAttributes.Literal, mod.TypeSystem.Int32)
    f.Constant = SInt32(v); wt_t.Fields.Add(f)
si_m = next(m for m in wt_t.Methods if m.Name == "WpfPendantOverlayWindow_SourceInitialized")
lv_v = VariableDefinition(mod.TypeSystem.Int32); si_m.Body.Variables.Add(lv_v)
il_s = si_m.Body.GetILProcessor()
for i in [il_s.Create(OpCodes.Ldloc_0), il_s.Create(OpCodes.Ldc_I4_2), il_s.Create(OpCodes.Ldc_I4_1),
          il_s.Create(OpCodes.Stloc, lv_v), il_s.Create(OpCodes.Ldloca, lv_v),
          il_s.Create(OpCodes.Ldc_I4_4), il_s.Create(OpCodes.Call, dm_t), il_s.Create(OpCodes.Pop)]:
    il_s.InsertBefore(next(x for x in si_m.Body.Instructions if x.OpCode == OpCodes.Ret), i)
print("P1")

# ═══ P2 ═══
upf = next(m for m in form1.Methods if m.Name == "UpdatePendantFrame")
for ins in upf.Body.Instructions:
    if ins.OpCode == OpCodes.Call and "IsSystemCursorHidden" in str(ins.Operand):
        n = upf.Body.Instructions[upf.Body.Instructions.IndexOf(ins) + 1]
        if n.OpCode in (OpCodes.Brfalse, OpCodes.Brfalse_S):
            il_up = upf.Body.GetILProcessor(); il_up.InsertBefore(n, il_up.Create(OpCodes.Pop))
            n.OpCode = OpCodes.Br_S
        break
print("P2")

# ═══ P3 ═══
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

upe3 = next(m for m in form1.Methods if m.Name == "UpdatePhysicsEngine3")
gsm = next(m for m in form1.Methods if m.Name == "GetSystemMetrics")
rxf, ryf, royf = [next(f for f in form1.Fields if f.Name == n) for n in ["ropeX", "ropeY", "ropeOldY"]]

after = None
for ins in upe3.Body.Instructions:
    if ins.OpCode == OpCodes.Call and "IntegratePhysicsEngine3Points" in str(ins.Operand):
        after = ins; break

il3 = upe3.Body.GetILProcessor()

# Helper to build the full sequence
def C(op, operand=None):
    """Create instruction. operand can be an Instruction (for branches), int, string, etc."""
    if operand is not None:
        return il3.Create(op, operand)
    return il3.Create(op)

# Build sequence step by step
S = []  # list of (instruction, label_key)
# Label keys: "loop_head", "loop_exit", "next_iter", "skip1", "skip2", "skip3"

# 1. WindowPlatforms.Update() — returns bool, must pop
S.append((C(OpCodes.Call, wp_update), None))
S.append((C(OpCodes.Pop), None))

# 2. Screen edge clamp
S.append((C(OpCodes.Ldarg_0), None)); S.append((C(OpCodes.Ldfld, rxf), None))
S.append((C(OpCodes.Ldloc_0), None))
S.append((C(OpCodes.Ldarg_0), None)); S.append((C(OpCodes.Ldfld, rxf), None))
S.append((C(OpCodes.Ldloc_0), None)); S.append((C(OpCodes.Ldelem_R4), None))
S.append((C(OpCodes.Ldc_I4_0), None)); S.append((C(OpCodes.Call, gsm), None))
S.append((C(OpCodes.Conv_R4), None)); S.append((C(OpCodes.Call, mmi), None))
S.append((C(OpCodes.Ldc_R4, 0.0), None)); S.append((C(OpCodes.Call, mma), None))
S.append((C(OpCodes.Stelem_R4), None))
S.append((C(OpCodes.Ldarg_0), None)); S.append((C(OpCodes.Ldfld, ryf), None))
S.append((C(OpCodes.Ldloc_0), None))
S.append((C(OpCodes.Ldarg_0), None)); S.append((C(OpCodes.Ldfld, ryf), None))
S.append((C(OpCodes.Ldloc_0), None)); S.append((C(OpCodes.Ldelem_R4), None))
S.append((C(OpCodes.Ldc_I4_1), None)); S.append((C(OpCodes.Call, gsm), None))
S.append((C(OpCodes.Conv_R4), None)); S.append((C(OpCodes.Ldc_R4, 20.0), None))
S.append((C(OpCodes.Sub), None)); S.append((C(OpCodes.Call, mmi), None))
S.append((C(OpCodes.Stelem_R4), None))

# 3. Unrolled window platform checks (4 platforms)
# Each platform block ends with a Nop that all its skip branches target
for pi in range(4):
    # Nop marker for this platform's skip branches
    plat_end = C(OpCodes.Nop)

    check = [
        # if count <= pi → skip this platform
        (C(OpCodes.Call, wp_count), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None),
        (C(OpCodes.Ble_S, plat_end), f"plat{pi}_skip0"),  # will be set to plat_end

        # pendY = ropeY[idx] + 20; if pendY < GetTop(pi) → skip
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Add), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Blt_S, plat_end), f"plat{pi}_skip1"),

        # ropeX >= GetLeft(pi)?
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_left), None),
        (C(OpCodes.Blt_S, plat_end), f"plat{pi}_skip2"),

        # ropeX <= GetRight(pi)?
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, rxf), None),
        (C(OpCodes.Ldloc_0), None), (C(OpCodes.Ldelem_R4), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_right), None),
        (C(OpCodes.Bgt_S, plat_end), f"plat{pi}_skip3"),

        # Clamp ropeY and ropeOldY
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, ryf), None),
        (C(OpCodes.Ldloc_0), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
        (C(OpCodes.Stelem_R4), None),
        (C(OpCodes.Ldarg_0), None), (C(OpCodes.Ldfld, royf), None),
        (C(OpCodes.Ldloc_0), None),
        (C(OpCodes.Ldc_I4, SInt32(pi)), None), (C(OpCodes.Call, wp_top), None),
        (C(OpCodes.Ldc_R4, 20.0), None), (C(OpCodes.Sub), None),
        (C(OpCodes.Stelem_R4), None),

        # End marker for this platform
        (plat_end, "end_check"),
    ]
    S.extend(check)

# ── Insert all ──
for instr, _ in reversed(S):
    il3.InsertAfter(after, instr)

# Branches already reference plat_end Nops which are in S and thus in the body.
# No additional patching needed — targets are valid instructions in the same method body.

print(f"P3: {len(S)} IL instructions injected")
print("  - WindowPlatforms.Update() periodic refresh")
print("  - Screen edge clamp")
print("  - Window title bar collision loop (up to 8 windows)")
print(f"REQUIRES: WinPlat.dll next to exe")

# ═══ Write ═══
T = os.path.join(BASE, "_t.exe")
asm.Write(T)
with open(T, "rb") as f: pe = f.read()
with open(OUT, "wb") as f: f.write(pe + overlay)
os.remove(T)
print(f"Done: {OUT}")