import os
import sys
import time
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
        "no-accel": if_match_and_remove("-na") or if_match_and_remove("--no-accel"),
        "convs": if_match_and_remove("-c") or if_match_and_remove("--convs"),
    }
    return options

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

def int_to_roman(n):
    roman_numerals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    result = ""
    for value, symbol in roman_numerals:
        while n >= value:
            result += symbol
            n -= value
    return result


# MAIN:

options = parse_options()

if options['help']:
    print("Available options:")
    print("-h, --help\t\tPrint this help menu.")
    print("-l, --live\t\tShow Timeloop's live status as it runs.")
    print("-na, --no-accel\tDo not use Accelergy, rely on stored ERT and ART from previous experiments.")
    print("-c, --convs\tRun experiments for convolutions rather than GEMMs.")
    sys.exit(0)

layer_dims = {
    "MB1": {
        'D':  8192,
        'E':  8192,
        'L':  8192
    },
    "MB2": {
        'D':  1024,
        'E':  8192,
        'L':  1024
    },
    "MB3": {
        'D':  8,
        'E':  8192,
        'L':  8
    },
    "MB4": {
        'D':  8,
        'E':  1024,
        'L':  8192
    },
    "MB5": {
        'D':  8192,
        'E':  1024,
        'L':  8
    },
    "MB6": {
        'D':  512,
        'E':  256,
        'L':  256
    },
    "Harsh1": {
        'D':  4000,
        'E':  6032,
        'L':  12000
    },
    "Harsh2": {
        'D':  7000,
        'E':  1440,
        'L':  4224
    }
}

bert_layers = ["KQV", "KTQ", "VScores", "FF1"]
MB_layers = [f"MB{i+1}" for i in range(6)]
harsh_layers = ["Harsh1", "Harsh2"]

convolutions_vgg = [f"vggL{i}" for i in range(16) if i not in (6, 9, 11, 12)] + ["vggL3+"]
convolutions_resnet = [f"resnetL{i}" for i in range(21) if i not in (2, 3, 4, 8, 9, 13, 14, 18, 19)] + ["resnetL1+", "resnetL3+"]
convolutions_benchmarks = [int_to_roman(i) for i in range(1, 18)]

if not options["convs"]:
    layers = bert_layers[0:1]# + MB_layers # + harsh_layers
else:
    layers = convolutions_benchmarks #+ convolutions_vgg + convolutions_resnet

print(f"Arguments provided: {sys.argv}")

archs = ["eyeriss", "simba_right", "tpu"]

# Define relative paths
ARCH_PATHs = {arch: f"{os.curdir}/arch/system_{arch}.yaml" for arch in archs}
COMPONENTS_PATH = f"{os.curdir}/arch/components/*.yaml"
if not options["convs"]:
    PROBLEM_PATHs = {layer: f"{os.curdir}/layers/{layer if layer in bert_layers else 'MB'}_layer.yaml" for layer in layers}
else:
    PROBLEM_PATHs = {}
    for layer in layers:
        if layer in convolutions_resnet:
            PROBLEM_PATHs[layer] = f"{os.curdir}/layers/resnet/{layer}_layer.yaml"
        elif layer in convolutions_vgg:
            PROBLEM_PATHs[layer] = f"{os.curdir}/layers/vgg/{layer}_layer.yaml"
        elif layer in convolutions_benchmarks:
            PROBLEM_PATHs[layer] = f"{os.curdir}/layers/conv_benchmarks/{layer}.yaml"
        else:
            raise Exception("Ehm, you likely f*cked up the specification of layers...")
MAPPER_PATH = f"{os.curdir}/mapper/mapper.yaml"
CONSTRAINTS_PATHs = {arch: f"{os.curdir}/constraints/constraints_{arch}.yaml" for arch in archs}
VARIABLES_PATH = f"{os.curdir}/mapper/variables.yaml"

#output_dir = f"{os.curdir}/outputs_experiments_across_archs_TLD/"
#output_dir = f"{os.curdir}/outputs_experiments_across_archs_TLL/"
#output_dir = f"{os.curdir}/outputs_experiments_across_archs_TLE/"
output_dir = f"{os.curdir}/outputs_experiments_across_archs_TLCD/"
#output_dir = f"{os.curdir}/outputs_experiments_across_archs_TLCL/"

ERT_PATHs = {arch: f"{output_dir}{arch}_{layers[0]}/timeloop-mapper.ERT.yaml" for arch in archs}
ART_PATHs = {arch: f"{output_dir}{arch}_{layers[0]}/timeloop-mapper.ART.yaml" for arch in archs}

for arch in archs:
    for layer in layers:
        ARCH_PATH = ARCH_PATHs[arch]
        PROBLEM_PATH = PROBLEM_PATHs[layer]
        CONSTRAINTS_PATH = CONSTRAINTS_PATHs[arch]
        ERT_PATH = ERT_PATHs[arch] 
        ART_PATH = ARCH_PATHs[arch]

        print(f"\n\nCurrently working on:\n - layer: {layer}\n - architecture: {arch}\n")

        print(f"Sources:\n- {ARCH_PATH}\n- {COMPONENTS_PATH}\n- {MAPPER_PATH}\n- {PROBLEM_PATH}\n- {CONSTRAINTS_PATH}\n- {VARIABLES_PATH}\n")

        if arch != "gemmini":
            spec = tl.Specification.from_yaml_files(
                ARCH_PATH,
                COMPONENTS_PATH,
                MAPPER_PATH,
                PROBLEM_PATH,
                #CONSTRAINTS_PATH, # constraints are used to enforce a specific mapping
                VARIABLES_PATH
            )
        else:
            spec = tl.Specification.from_yaml_files(
                ARCH_PATH,
                COMPONENTS_PATH,
                MAPPER_PATH,
                PROBLEM_PATH,
                f"{os.curdir}/constraints/constraints.yaml",
                VARIABLES_PATH
            )

        if layer not in bert_layers and not options["convs"]:
            for k in layer_dims[layer].keys():
                spec.variables["MB_" + k] = layer_dims[layer][k]

        if options['live']:
            spec.mapper.live_status = True

        spec.mapspace.template = 'uber' #'ruby'

        current_output_dir = output_dir + arch + "_" + layer
        if not os.path.exists(current_output_dir): os.makedirs(current_output_dir)
        start_time = time.time()
        try:
            extra_input_files = [ART_PATH, ERT_PATH] if options["no-accel"] else []
            tl.call_mapper(spec, output_dir=current_output_dir, extra_input_files=extra_input_files)  # Run the Timeloop mapper
            execution_time = time.time() - start_time
            print(f"\nTimeloop finished in: {execution_time:.3f}s")

            append_to_file(f"{current_output_dir}/timeloop-mapper.stats.txt", f"Execution time:\t{execution_time:.3f}")
            print("\n\nMapping:")
            print(read_and_indent(f"{current_output_dir}/timeloop-mapper.map.txt"))
        except Exception as e:
            print(f"EXCEPTION: {e}")
            print(f"\n\n------------> ERROR!! Mapping failed for layer ->{layer}<- on arch {arch}")