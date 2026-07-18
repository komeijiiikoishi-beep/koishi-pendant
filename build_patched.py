"""
Build patched 恋恋挂件 from original v1 exe.
Requires: Mono.Cecil at C:\Users\LENOVO\Downloads\mono.cecil\lib\net40\
Patches: P1 DWM shadow fix, P2 cursor freeze
Usage: python build_patched.py
Output: 恋恋挂件_patched_v6.exe
"""
import clr, sys, os
sys.path.append(r"C:\Users\LENOVO\Downloads\mono.cecil\lib\net40")
clr.AddReference("Mono.Cecil")
from Mono.Cecil import *
from Mono.Cecil.Cil import *
from System import Int32 as SInt32

BASE = os.path.dirname(os.path.abspath(__file__))
ORIGINAL = os.path.join(BASE, "恋恋挂件-本地测试版-v1.exe")
OUTPUT = os.path.join(BASE, "恋恋挂件_patched_v6.exe")
OVERLAY_OFFSET = 581632

# Extract overlay
with open(ORIGINAL, "rb") as f:
    original_data = f.read()
overlay = original_data[OVERLAY_OFFSET:]
print(f"Overlay: {len(overlay)} bytes")

asm = AssemblyDefinition.ReadAssembly(ORIGINAL)
mod = asm.MainModule

# ═══ P1: DWM Shadow Fix ═══
win_type = next(t for t in mod.Types if t.Name == "WpfPendantOverlayWindow")

ref_int32 = ByReferenceType(mod.TypeSystem.Int32)
dwmapi_ref = ModuleReference("dwmapi.dll")
mod.ModuleReferences.Add(dwmapi_ref)

dwm_method = MethodDefinition(
    "DwmSetWindowAttribute",
    MethodAttributes.PInvokeImpl | MethodAttributes.Static | MethodAttributes.Private,
    mod.TypeSystem.Int32,
)
pa = getattr(ParameterAttributes, "None")
dwm_method.Parameters.Add(ParameterDefinition("hwnd", pa, mod.TypeSystem.IntPtr))
dwm_method.Parameters.Add(ParameterDefinition("dwAttribute", pa, mod.TypeSystem.Int32))
dwm_method.Parameters.Add(ParameterDefinition("pvAttribute", pa, ref_int32))
dwm_method.Parameters.Add(ParameterDefinition("cbAttribute", pa, mod.TypeSystem.Int32))
dwm_method.PInvokeInfo = PInvokeInfo(
    PInvokeAttributes.CallConvWinapi, "DwmSetWindowAttribute", dwmapi_ref
)
dwm_method.ImplAttributes = MethodImplAttributes.PreserveSig
win_type.Methods.Add(dwm_method)

for name, val in [("DWMWA_NCRENDERING_POLICY", 2), ("DWMNCRP_DISABLED", 1)]:
    fld = FieldDefinition(
        name,
        FieldAttributes.Static | FieldAttributes.Private | FieldAttributes.Literal,
        mod.TypeSystem.Int32,
    )
    fld.Constant = SInt32(val)
    win_type.Fields.Add(fld)

si = next(m for m in win_type.Methods if m.Name == "WpfPendantOverlayWindow_SourceInitialized")
dwm_local = VariableDefinition(mod.TypeSystem.Int32)
si.Body.Variables.Add(dwm_local)
il = si.Body.GetILProcessor()
ret = next(i for i in si.Body.Instructions if i.OpCode == OpCodes.Ret)
call_seq = [
    il.Create(OpCodes.Ldloc_0),
    il.Create(OpCodes.Ldc_I4_2),
    il.Create(OpCodes.Ldc_I4_1),
    il.Create(OpCodes.Stloc, dwm_local),
    il.Create(OpCodes.Ldloca, dwm_local),
    il.Create(OpCodes.Ldc_I4_4),
    il.Create(OpCodes.Call, dwm_method),
    il.Create(OpCodes.Pop),
]
for i in call_seq:
    il.InsertBefore(ret, i)
print("P1: DWM shadow fix injected")

# ═══ P2: Cursor Freeze ═══
form1 = next(t for t in mod.Types if t.Name == "Form1")
upf = next(m for m in form1.Methods if m.Name == "UpdatePendantFrame")
for instr in upf.Body.Instructions:
    if instr.OpCode == OpCodes.Call and "IsSystemCursorHidden" in str(instr.Operand):
        nxt = upf.Body.Instructions[upf.Body.Instructions.IndexOf(instr) + 1]
        if nxt.OpCode in (OpCodes.Brfalse, OpCodes.Brfalse_S):
            il2 = upf.Body.GetILProcessor()
            il2.InsertBefore(nxt, il2.Create(OpCodes.Pop))
            nxt.OpCode = OpCodes.Br_S
            print("P2: cursor freeze injected (pop + br.s)")
        break

# ═══ Write ═══
TEMP = os.path.join(BASE, "_temp.exe")
asm.Write(TEMP)
with open(TEMP, "rb") as f:
    pe = f.read()
with open(OUTPUT, "wb") as f:
    f.write(pe + overlay)
os.remove(TEMP)
print(f"Done: {OUTPUT}  ({len(pe) + len(overlay)} bytes)")
