import os
import sys
import timeloopfe.v4 as tl

# L = inputs cols
# E = inner dimension
# D = weights rows

def if_match_and_remove(flag, with_value = False):
    try:
        idx = sys.argv.index(flag)
        sys.argv.pop(idx)
        if with_value:
            return sys.argv.pop(idx)
        else:
            return True
        return
    except:
        return False

def parse_options():
    options = {
        "help": if_match_and_remove("-h") or if_match_and_remove("--help"),
        "live": if_match_and_remove("-l") or if_match_and_remove("--live"),
        "no_e_fusion": if_match_and_remove("-nef") or if_match_and_remove("--no_e_fusion"),
        "l_fusion": if_match_and_remove("-lf") or if_match_and_remove("--l_fusion")
    }
    return options

options = parse_options()

if options['help']:
    print("Available options:")
    print("-h, --help\t\tprint this help menu.")
    print("-l, --live\t\tshow Timeloop's live status as it runs.")
    print("-nef, --no_e_fusion\tdo not enforce E=1 when doing fusions (useful only on matmul layers).")
    print("\t\t\t[Increases the latency with which column vectors are ready, due to DRAM accesses]")
    print("-lf, --l_fusion\t\tenforce L=1 when doing fusions (useful only on matmul layers).")
    print("\t\t\t[Stores the entirety of the output in the Accumulator, useful NO execution\n\t\t\tdoes not overlap with the matmul, but happens later]")
    sys.exit(0)

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
is_fusion = len(sys.argv) == 3
level_for_fusion = memory_levels.index(sys.argv[2]) if is_fusion else 0

# Define relative paths
ARCH_PATH = f"{os.curdir}/arch_v0.4/system_PIM{'_NOs' if is_norm_op else ''}.yaml"
COMPONENTS_PATH = f"{os.curdir}/arch_v0.4/components/*.yaml"
PROBLEM_PATH = f"{os.curdir}/layers/{sys.argv[1]}_layer.yaml"
MAPPER_PATH = f"{os.curdir}/mapper/mapper.yaml"
CONSTRAINTS_PATH = f"{os.curdir}/constraints_v0.4/constraints{'_NOs' if is_norm_op else ''}.yaml"
VARIABLES_PATH = f"{os.curdir}/mapper/variables.yaml"

print(f"Sources:\n- {ARCH_PATH}\n- {COMPONENTS_PATH}\n- {MAPPER_PATH}\n- {PROBLEM_PATH}\n- {CONSTRAINTS_PATH}\n- {VARIABLES_PATH}\n")

spec = tl.Specification.from_yaml_files(
    ARCH_PATH,
    COMPONENTS_PATH,
    MAPPER_PATH,
    PROBLEM_PATH,
    CONSTRAINTS_PATH,
    VARIABLES_PATH
)  # Gather YAML files into a Python object

constrained_factors = ["D=1"]
if not options['no_e_fusion']: constrained_factors.append("E=1")
if options['l_fusion']: constrained_factors.append("L=1")

if spec.constraints['targets'] is None:
    spec.constraints['targets'] = tl.constraints.ConstraintsList()
if is_fusion:
    if not is_norm_op:
        # Apply fusion constraints
        found = []
        for target in spec.constraints['targets']:
            if target['target'] in memory_levels[0:level_for_fusion] and target['target'] not in found and target.type == "temporal":
                found.append(target['target'])
                target.factors = constrained_factors
                print(f"Updating constraint: {dict(target.items())}")
        for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion])):
            spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': target, 'type': 'temporal', 'factors': constrained_factors}))
            print(f"Adding constraint: {dict(spec.constraints['targets'][-1].items())}")
        found.clear()
        # THE LEVEL AT WHICH YOU FUSE MUST HAVE LOOPS (inner)EDL(outer)
        for target in spec.constraints['targets']:
            if target['target'] in memory_levels[0:level_for_fusion+1] and target['target'] and target['type'] == "temporal":
                found.append(target['target'])
                target['permutation'] = tl.constraints.Permutation(['E', 'D', 'L'])
                print(f"Updating constraint: {dict(target.items())}")
                break
        for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion+1])):
            spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': memory_levels[level_for_fusion], 'type': 'temporal', 'permutation': ['E', 'D', 'L']}))
            print(f"Adding constraint: {dict(spec.constraints['targets'][-1].items())}")
    
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
                print(f"Updating constraint: {dict(target.items())}")
        for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion])):
            spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': target, 'type': 'dataspace', 'bypass': ["Inputs", "Weights", "Outputs"]}))
            print(f"Adding constraint: {dict(spec.constraints['targets'][-1].items())}")

if options['live']:
    spec.mapper.live_status = True

spec.mapspace.template = 'uber' #'ruby'

output_dir = f"{os.curdir}/outputs_{sys.argv[1]}" + (("_" + sys.argv[2]) if level_for_fusion else "")
if not os.path.exists(output_dir): os.makedirs(output_dir)
tl.call_mapper(spec, output_dir=output_dir)  # Run the Timeloop mapper

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

def append_to_file(path, text_to_append):
    with open(path, 'a') as file:
        file.write('\n\n' + text_to_append)

append_to_file(f"{output_dir}/timeloop-mapper.map.txt", f"Fusion optimized: {is_fusion}\nFusion constraints: {constrained_factors}")
print("\n\nMapping:")
print(read_and_indent(f"{output_dir}/timeloop-mapper.map.txt"))
