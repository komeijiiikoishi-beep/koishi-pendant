"""Stable build: P1(DWM) + P2(freeze) + P3(screen edge clamp). Pure IL, no DLL."""
import clr, sys, os
sys.path.append(r"C:\Users\LENOVO\Downloads\mono.cecil\lib\net40")
clr.AddReference("Mono.Cecil")
from Mono.Cecil import *
from Mono.Cecil.Cil import *
from System import Int32 as SInt32

BASE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(BASE, "恋恋挂件-本地测试版-v1.exe")
OUT = os.path.join(BASE, "恋恋挂件_stable.exe")
OVERLAY_OFFSET = 581632

with open(ORIG, "rb") as f: overlay = f.read()[OVERLAY_OFFSET:]
asm = AssemblyDefinition.ReadAssembly(ORIG); mod = asm.MainModule
PA = getattr(ParameterAttributes, "None")
form1 = next(t for t in mod.Types if t.Name == "Form1")

# P1
wt = next(t for t in mod.Types if t.Name == "WpfPendantOverlayWindow")
ri = ByReferenceType(mod.TypeSystem.Int32)
dr = ModuleReference("dwmapi.dll"); mod.ModuleReferences.Add(dr)
dm = MethodDefinition("DwmSetWindowAttribute", MethodAttributes.PInvokeImpl | MethodAttributes.Static | MethodAttributes.Private, mod.TypeSystem.Int32)
for n, t in [("hwnd", mod.TypeSystem.IntPtr), ("dwAttribute", mod.TypeSystem.Int32), ("pvAttribute", ri), ("cbAttribute", mod.TypeSystem.Int32)]:
    dm.Parameters.Add(ParameterDefinition(n, PA, t))
dm.PInvokeInfo = PInvokeInfo(PInvokeAttributes.CallConvWinapi, "DwmSetWindowAttribute", dr)
dm.ImplAttributes = MethodImplAttributes.PreserveSig; wt.Methods.Add(dm)
for n, v in [("DWMWA_NCRENDERING_POLICY", 2), ("DWMNCRP_DISABLED", 1)]:
    f = FieldDefinition(n, FieldAttributes.Static | FieldAttributes.Private | FieldAttributes.Literal, mod.TypeSystem.Int32)
    f.Constant = SInt32(v); wt.Fields.Add(f)
si_m = next(m for m in wt.Methods if m.Name == "WpfPendantOverlayWindow_SourceInitialized")
lv_v = VariableDefinition(mod.TypeSystem.Int32); si_m.Body.Variables.Add(lv_v)
il_s = si_m.Body.GetILProcessor()
for i in [il_s.Create(OpCodes.Ldloc_0), il_s.Create(OpCodes.Ldc_I4_2), il_s.Create(OpCodes.Ldc_I4_1),
          il_s.Create(OpCodes.Stloc, lv_v), il_s.Create(OpCodes.Ldloca, lv_v),
          il_s.Create(OpCodes.Ldc_I4_4), il_s.Create(OpCodes.Call, dm), il_s.Create(OpCodes.Pop)]:
    il_s.InsertBefore(next(x for x in si_m.Body.Instructions if x.OpCode == OpCodes.Ret), i)
print("P1: DWM")

# P2
upf = next(m for m in form1.Methods if m.Name == "UpdatePendantFrame")
for ins in upf.Body.Instructions:
    if ins.OpCode == OpCodes.Call and "IsSystemCursorHidden" in str(ins.Operand):
        n = upf.Body.Instructions[upf.Body.Instructions.IndexOf(ins) + 1]
        if n.OpCode in (OpCodes.Brfalse, OpCodes.Brfalse_S):
            il_u = upf.Body.GetILProcessor(); il_u.InsertBefore(n, il_u.Create(OpCodes.Pop))
            n.OpCode = OpCodes.Br_S; print("P2: freeze")
        break

# P3: Screen edge clamp only
upe3 = next(m for m in form1.Methods if m.Name == "UpdatePhysicsEngine3")
gsm = next(m for m in form1.Methods if m.Name == "GetSystemMetrics")
rxf = next(f for f in form1.Fields if f.Name == "ropeX")
ryf = next(f for f in form1.Fields if f.Name == "ropeY")

msr = next(r for r in mod.AssemblyReferences if r.Name == "mscorlib")
mtr = TypeReference("System", "Math", mod, msr).Resolve()
mmi = mod.ImportReference(next(m for m in mtr.Methods if m.Name == "Min" and m.Parameters.Count == 2 and m.Parameters[0].ParameterType.FullName == "System.Single"))
mma = mod.ImportReference(next(m for m in mtr.Methods if m.Name == "Max" and m.Parameters.Count == 2 and m.Parameters[0].ParameterType.FullName == "System.Single"))

after = None
for ins in upe3.Body.Instructions:
    if ins.OpCode == OpCodes.Call and "IntegratePhysicsEngine3Points" in str(ins.Operand):
        after = ins; break

il3 = upe3.Body.GetILProcessor()

# X: Max(0, Min(ropeX[i], screenW))
# Y: Min(ropeY[i], screenH - 20)
clamp = [
    il3.Create(OpCodes.Ldarg_0), il3.Create(OpCodes.Ldfld, rxf), il3.Create(OpCodes.Ldloc_0),
    il3.Create(OpCodes.Ldarg_0), il3.Create(OpCodes.Ldfld, rxf), il3.Create(OpCodes.Ldloc_0),
    il3.Create(OpCodes.Ldelem_R4),
    il3.Create(OpCodes.Ldc_I4_0), il3.Create(OpCodes.Call, gsm), il3.Create(OpCodes.Conv_R4),
    il3.Create(OpCodes.Call, mmi),
    il3.Create(OpCodes.Ldc_R4, 0.0), il3.Create(OpCodes.Call, mma),
    il3.Create(OpCodes.Stelem_R4),
    il3.Create(OpCodes.Ldarg_0), il3.Create(OpCodes.Ldfld, ryf), il3.Create(OpCodes.Ldloc_0),
    il3.Create(OpCodes.Ldarg_0), il3.Create(OpCodes.Ldfld, ryf), il3.Create(OpCodes.Ldloc_0),
    il3.Create(OpCodes.Ldelem_R4),
    il3.Create(OpCodes.Ldc_I4_1), il3.Create(OpCodes.Call, gsm), il3.Create(OpCodes.Conv_R4),
    il3.Create(OpCodes.Ldc_R4, 20.0), il3.Create(OpCodes.Sub), il3.Create(OpCodes.Call, mmi),
    il3.Create(OpCodes.Stelem_R4),
]

for i in reversed(clamp):
    il3.InsertAfter(after, i)

print("P3: screen edge clamp")

T = os.path.join(BASE, "_t.exe"); asm.Write(T)
with open(T, "rb") as f: pe = f.read()
with open(OUT, "wb") as f: f.write(pe + overlay)
os.remove(T)
print(f"Done: {OUT}")
