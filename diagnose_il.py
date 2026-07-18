"""
Diagnostic: Dump IL of key methods from the original EXE to understand:
1. What ldloc.0 is in UpdatePhysicsEngine3 (pendant index or loop counter?)
2. Structure of FreezePhysicsEngine3AtRest (to verify P4c injection safety)
3. IntegratePhysicsEngine3Points call site (to verify P3 insertion point)
"""
import clr, sys, os
sys.path.append(r"C:\Users\LENOVO\Downloads\mono.cecil\lib\net40")
clr.AddReference("Mono.Cecil")
from Mono.Cecil import *
from Mono.Cecil.Cil import *

BASE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(BASE, "恋恋挂件-本地测试版-v1.exe")

asm = AssemblyDefinition.ReadAssembly(ORIG)
mod = asm.MainModule
form1 = next(t for t in mod.Types if t.Name == "Form1")

def dump_method(method, max_lines=200):
    """Print method signature, locals, and IL body"""
    print(f"\n{'='*70}")
    print(f"Method: {method.Name}")
    print(f"Signature: {method.FullName}")
    print(f"Locals ({len(method.Body.Variables)}):")
    for i in range(method.Body.Variables.Count):
        v = method.Body.Variables[i]
        print(f"  [{i}] {v.VariableType.FullName}")
    print(f"\nIL ({method.Body.Instructions.Count} instructions):")
    count = 0
    for ins in method.Body.Instructions:
        if count >= max_lines: break
        op = ins.OpCode
        operand = ins.Operand
        if operand is None:
            print(f"  IL_{ins.Offset:04X}: {op}")
        elif isinstance(operand, FieldReference):
            print(f"  IL_{ins.Offset:04X}: {op} {operand.DeclaringType.Name}::{operand.Name}")
        elif isinstance(operand, MethodReference):
            print(f"  IL_{ins.Offset:04X}: {op} {operand.DeclaringType.Name}::{operand.Name}()")
        elif isinstance(operand, TypeReference):
            print(f"  IL_{ins.Offset:04X}: {op} {operand.FullName}")
        elif isinstance(operand, str):
            print(f"  IL_{ins.Offset:04X}: {op} \"{operand}\"")
        else:
            print(f"  IL_{ins.Offset:04X}: {op} {operand}")
        count += 1
    if method.Body.Instructions.Count > max_lines:
        print(f"  ... ({method.Body.Instructions.Count - max_lines} more)")

# ── Key methods to inspect ──
targets = [
    "UpdatePhysicsEngine3",
    "FreezePhysicsEngine3AtRest",
    "TryFreezePhysicsEngine3AtRest",
    "IntegratePhysicsEngine3Points",
    "GetPhysicsEngine3PendantDamping",
]

for name in targets:
    try:
        m = next(m for m in form1.Methods if m.Name == name)
        dump_method(m, max_lines=250)
    except StopIteration:
        print(f"\nMethod '{name}' NOT FOUND in Form1")

# ── Also dump all fields (to understand rope arrays) ──
print(f"\n{'='*70}")
print("Form1 Fields (rope-related):")
for f in form1.Fields:
    if "rope" in f.Name.lower() or "pendant" in f.Name.lower() or "segment" in f.Name.lower():
        print(f"  {f.FieldType.FullName} {f.Name}")

print(f"\n{'='*70}")
print("Form1 Fields (ALL):")
for f in form1.Fields:
    print(f"  {f.FieldType.FullName} {f.Name}")
