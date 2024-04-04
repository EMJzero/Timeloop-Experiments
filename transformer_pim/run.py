import os
import sys
import timeloopfe.v4 as tl

# L = inputs cols
# E = inner dimension
# D = weights rows

matmuls = ["KQV", "KTQ", "VScores", "Out", "FF1", "FF2"]
normops = ["softmax", "layernorm"]

valid_args_1 = matmuls + normops
desc_1 = [
    "First matmul, computes Q, K and V from Input with a projection.",
    "Second matmul, computes Scores as K^T*Q.",
    "Third matmul, computes V' with the convex combinations in V*Scores.",
    "Fourth matmul, computes Out from V' with a projection.",
    "Fifth matmul, first projection of the FF block, increases the latent dimension.",
    "Sixth matmul, second projection of the FF block, decreases back the latent dimension."
]

# MUST STAY ORDERED! Set D,E=1 for all those above the specified one!
memory_levels = ["DRAM", "shared_glb", "scratchpad"]
desc_memory_levels = [
    "DRAM, off-chip storage, fusing here is the same as doing nothing XD.",
    "Global buffer, main on-chip SRAM storage, usual target for fusions.",
    "Scratchpad simulating the IMC SRAM, fusion possible iif all weights can fit it at once."
]

if len(sys.argv) not in [2, 3] or sys.argv[1] not in valid_args_1 or (len(sys.argv) == 3 and sys.argv[2] not in memory_levels):
    print("Error: Invalid argument(s).")
    print(f"Argvs: {sys.argv}")
    print("First argument must be one of the following:\n- {}".format('\n- '.join([a + ': ' + d for a, d in zip(valid_args_1, desc_1)])))
    print("Second argument can be the name of the memory hierarchy level at which to prepare for column-wise operation fusion. Hence one of the following:\n- {}".format('\n- '.join([a + ': ' + d for a, d in zip(memory_levels, desc_memory_levels)])))
    sys.exit(1)

print(f"Arguments provided: {sys.argv}")

is_norm_op = sys.argv[1] in normops
level_for_fusion = memory_levels.index(sys.argv[2]) if len(sys.argv) == 3 else 0

# Define relative paths
ARCH_PATH = f"{os.curdir}/arch_v0.4/system_PIM{'_NOs' if is_norm_op else ''}.yaml"
COMPONENTS_PATH = f"{os.curdir}/arch_v0.4/components/*.yaml"
PROBLEM_PATH = f"{os.curdir}/layers/{sys.argv[1]}_layer.yaml"
MAPPER_PATH = f"{os.curdir}/mapper/mapper.yaml"
CONSTRAINTS_PATH = f"{os.curdir}/constraints_v0.4/constraints{'_NOs' if is_norm_op else ''}.yaml"
VARIABLES_PATH = f"{os.curdir}/mapper/variables.yaml"

spec = tl.Specification.from_yaml_files(
    ARCH_PATH,
    COMPONENTS_PATH,
    MAPPER_PATH,
    PROBLEM_PATH,
    CONSTRAINTS_PATH,
    VARIABLES_PATH
)  # Gather YAML files into a Python object

if spec.constraints['targets'] is None:
    spec.constraints['targets'] = tl.constraints.ConstraintsList()
if not is_norm_op:
    # Apply fusion constraints
    found = []
    for target in spec.constraints['targets']:
        if target['target'] in memory_levels[0:level_for_fusion] and target['target'] not in found and target.type == "temporal":
            found.append(target['target'])
            target.factors = ["D=1", "E=1"]
    for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion])):
        spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': target, 'type': 'temporal', 'factors': ['D=1', 'E=1']}))
if is_norm_op:
    print("WARNING: copying just the bypasses, disregarding latency between two columns being ready. This means that only energy is a valid estimate.")
    # Apply the fusion to the NO
    found = []
    for target in spec.constraints['targets']:
        if target['target'] in memory_levels[0:level_for_fusion] and target['target'] not in found and target.type == "dataspace":
            found.append(target['target'])
            if "Inputs" not in target['bypass']:
                target.bypass.append("Inputs")
            if "Inputs" in target['keep']:
                target.keep.remove("Inputs")
    for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion])):
        spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': target, 'type': 'dataspace', 'bypass': ["Inputs", "Weights", "Outputs"]}))

if not os.path.exists(f"{os.curdir}/outputs_{sys.argv[1]}"): os.makedirs(f"{os.curdir}/outputs_{sys.argv[1]}")
tl.call_mapper(spec, output_dir=f"{os.curdir}/outputs_{sys.argv[1]}")  # Run the Timeloop mapper

#stats = open("outputs/timeloop-mapper.stats.txt").read()
#print(stats[stats.index("Summary Stats") :])

def read_and_indent(path, n_lines=30, start_at: str = None, end_at: str = None):
    content = open(path).read()
    if start_at is not None:
        content = content[content.index(start_at) :]
    if end_at is not None:
        content = content[: content.index(end_at) + len(end_at)]
    content = content.split("\n")
    content = content[:n_lines] if n_lines > 0 else content[n_lines:]
    return "\t" + "\n\t".join(content)


print("\n\nMapping:")
print(read_and_indent(f"{os.curdir}/outputs_{sys.argv[1]}/timeloop-mapper.map.txt"))

