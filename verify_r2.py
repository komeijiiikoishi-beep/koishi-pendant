"""
Verify r2.exe: Check FreezePhysicsEngine3AtRest and UpdatePhysicsEngine3
IL for obvious stack imbalance and structural corruption.
"""
import clr, sys, os
sys.path.append(r"C:\Users\LENOVO\Downloads\mono.cecil\lib\net40")
clr.AddReference("Mono.Cecil")
from Mono.Cecil import *
from Mono.Cecil.Cil import *

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(BASE, "恋恋挂件_r2.exe")

asm = AssemblyDefinition.ReadAssembly(TARGET)
mod = asm.MainModule
form1 = next(t for t in mod.Types if t.Name == "Form1")

def dump_method_il(method, max_lines=400):
    """Dump IL with stack states"""
    print(f"\n{'='*70}")
    print(f"Method: {method.Name}")
    print(f"Locals: {method.Body.Variables.Count}")
    for i in range(method.Body.Variables.Count):
        v = method.Body.Variables[i]
        vt = str(v.VariableType)
        if "Single" in vt:
            print(f"  [{i}] float (patched)")
        else:
            print(f"  [{i}] {vt}")
    print(f"IL: {method.Body.Instructions.Count} instructions")
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
        elif isinstance(operand, VariableDefinition):
            print(f"  IL_{ins.Offset:04X}: {op} V_{operand.Index}")
        elif isinstance(operand, Instruction):
            print(f"  IL_{ins.Offset:04X}: {op} -> IL_{operand.Offset:04X}")
        elif isinstance(operand, ParameterDefinition):
            print(f"  IL_{ins.Offset:04X}: {op} {operand.Name}")
        else:
            print(f"  IL_{ins.Offset:04X}: {op} {operand}")
        count += 1
    if method.Body.Instructions.Count > max_lines:
        print(f"  ... ({method.Body.Instructions.Count - max_lines} more)")

# Stack behaviour enum values from Mono.Cecil
# Pop0=0, Pop1=1, Pop1_pop1=2, Popi=3, Popi_pop1=4, Popi_popi=5, Popi_popi8=6,
# Popi_popi_popi=7, Popi_popr4=8, Popi_popr8=9, Popref=10, Popref_pop1=11,
# Popref_popi=12, Popref_popi_popi=13, Popref_popi_popi8=14, Popref_popi_popr4=15,
# Popref_popi_popr8=16, Popref_popi_popref=17, PopAll=18,
# Push0=20, Push1=21, Push1_push1=22, Pushi=23, Pushi8=24, Pushr4=25, Pushr8=26,
# Pushref=27, Varpop=28, Varpush=29

def estimate_stack(instructions):
    """Rough stack depth. Returns (max_depth, final_depth, errors)"""
    depth = 0
    max_depth = 0
    errors = []
    for ins in instructions:
        op = ins.OpCode
        sbp = int(op.StackBehaviourPop)
        sbpush = int(op.StackBehaviourPush)

        # pop
        if sbp in (1, 10):  # Pop1, Popref
            depth -= 1
        elif sbp in (2, 11):  # Pop1_pop1, Popref_pop1
            depth -= 2
        elif sbp == 18:  # PopAll
            depth = 0
        elif sbp in (3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17):  # Popi variants
            if op in (OpCodes.Call, OpCodes.Callvirt, OpCodes.Newobj):
                operand = ins.Operand
                if operand and hasattr(operand, 'Parameters'):
                    num_params = operand.Parameters.Count
                    depth -= num_params
                    # instance methods also pop 'this'
                    if hasattr(operand, 'HasThis') and operand.HasThis:
                        depth -= 1
                elif op == OpCodes.Newobj:
                    if operand and hasattr(operand, 'Parameters'):
                        depth -= operand.Parameters.Count
                else:
                    depth -= 1  # conservative
            elif op == OpCodes.Ret:
                pass  # ret pops 0 or 1 depending on return type
            elif op == OpCodes.Ldelem_R4 or op == OpCodes.Ldelem_I4:
                depth -= 2  # array + index
                depth += 1  # result (counted below)
            elif op == OpCodes.Stelem_R4 or op == OpCodes.Stelem_I4:
                depth -= 3  # array + index + value
            else:
                depth -= 2  # conservative guess

        # push
        if sbpush == 21:  # Push1
            depth += 1
        elif sbpush == 22:  # Push1_push1
            depth += 2
        elif sbpush in (25, 26, 27):  # Pushr4, Pushr8, Pushref
            depth += 1
        elif sbpush == 29:  # Varpush
            if op == OpCodes.Call or op == OpCodes.Callvirt:
                operand = ins.Operand
                if operand and hasattr(operand, 'ReturnType'):
                    if str(operand.ReturnType) != "System.Void":
                        depth += 1
                else:
                    depth += 1
            elif op == OpCodes.Ldloc or op == OpCodes.Ldarg or op == OpCodes.Ldsfld:
                depth += 1
            elif op == OpCodes.Ldelem_R4:
                pass  # already handled above
            elif op == OpCodes.Newarr:
                depth += 1  # length consumed, reference pushed
            else:
                depth += 1  # conservative

        if depth < 0 and op != OpCodes.Ret:
            errors.append(f"UNDERFLOW at IL_{ins.Offset:04X}: {op} (depth={depth})")
        if depth > max_depth:
            max_depth = depth

    return max_depth, depth, errors

# ═══ Check key methods ═══
for name in ["FreezePhysicsEngine3AtRest", "UpdatePhysicsEngine3"]:
    try:
        m = next(m for m in form1.Methods if m.Name == name)
        dump_method_il(m)
        max_d, final_d, errs = estimate_stack(m.Body.Instructions)
        print(f"\n  Stack: max={max_d}, final={final_d}")
        for e in errs:
            print(f"  ⚠ {e}")
    except StopIteration:
        print(f"\nMethod '{name}' NOT FOUND")

# ═══ Structural validation ═══
print(f"\n{'='*70}")
print("Structural validation:")
total_errs = 0
for name in ["UpdatePhysicsEngine3", "FreezePhysicsEngine3AtRest", "TryFreezePhysicsEngine3AtRest"]:
    m = next(m for m in form1.Methods if m.Name == name)
    print(f"  {name}: {m.Body.Instructions.Count} IL, {m.Body.Variables.Count} locals")

    # Check all branch targets exist
    branch_errs = 0
    for ins in m.Body.Instructions:
        if ins.Operand and isinstance(ins.Operand, Instruction):
            target = ins.Operand
            if target not in m.Body.Instructions:
                print(f"    ⚠ DANGLING BRANCH: IL_{ins.Offset:04X} -> missing target")
                branch_errs += 1
    if branch_errs == 0:
        print(f"    ✓ All branch targets valid")
    total_errs += branch_errs

# ═══ Check added fields ═══
print(f"\nAdded fields:")
for f in form1.Fields:
    if "frozenMicro" in f.Name:
        print(f"  ✓ {f.Name} ({f.FieldType.FullName})")

if total_errs == 0:
    print(f"\n✓ No structural issues found")
else:
    print(f"\n⚠ {total_errs} structural issues found")
print("Done.")
