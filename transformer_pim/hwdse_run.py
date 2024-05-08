import timeloopfe.v4 as tl
import itertools
import signal
import code
import math
import sys
import os

from prettytable import PrettyTable
import json
import time
import re

# L = inputs cols
# E = inner dimension
# D = weights rows

in_interactive_mode = False

def signal_handler(sig, frame):
    global in_interactive_mode
    if in_interactive_mode:
        print('EXITING...')
        sys.exit(0)
    else:
        print('\nHANDLING TERMINATION...\n')
        time.sleep(0.2)
        print('\nTERMINATION RECEIVED - SWITCHING TO INTERACTIVE MODE\n[type "exit()" or press "ctrl+c" again to terminate the program]\n')
        in_interactive_mode = True
        code.interact(local=globals())
        in_interactive_mode = False

signal.signal(signal.SIGINT, signal_handler)

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
        "l_fusion": if_match_and_remove("-lf") or if_match_and_remove("--l_fusion"),
        "pay_writeback_in_matmul": if_match_and_remove("-pwim") or if_match_and_remove("--pay_wb_in_mm"),
        "mixup": if_match_and_remove("-mx") or if_match_and_remove("--mixup"),
        "victory_condition": if_match_and_remove("-vc", True) or if_match_and_remove("--vict_cond", True),
        "summary_only": if_match_and_remove("-so") or if_match_and_remove("--summary_only"),
        "table": if_match_and_remove("-t") or if_match_and_remove("--table"),
        "initial_idx": if_match_and_remove("-i", True) or if_match_and_remove("--init_idx"),
        "ignore_heads": if_match_and_remove("-ih") or if_match_and_remove("--ignore_heads"),
        "imperfect_fact": if_match_and_remove("-if") or if_match_and_remove("--imperfect_fact")
    }
    return options

print(f"Arguments provided: {sys.argv}")
options = parse_options()

# Print the help menu and quit
if options['help']:
    print("Available options:")
    print("-h, --help\t\tPrint this help menu.")
    print("-l, --live\t\tShow Timeloop's live status as it runs.")
    print("-nef, --no_e_fusion\tDo not enforce E=1 when doing fusions (useful only on matmul layers).")
    print("\t\t\t[Increases the latency with which column vectors are ready, due to DRAM accesses]")
    print("-lf, --l_fusion\t\tEnforce L=1 when doing fusions (useful only on matmul layers).")
    print("\t\t\t[Stores the entirety of the output in the Accumulator, useful if NO execution\n\t\t\tdoes not overlap with the matmul, but happens later]")
    print("-pwim, --pay_wb_in_mm\tWhen fusing, moves estimation of the cost of writing the final output from the NOs to the matmul.")
    print("\t\t\t[Essentially, now the matmul writes to DRAM, and the NO simply operates to and from on-chip memories]")
    print("-mx, --mixup\t\tInstead of trying only hardcoded hardware configurations, also try any permutation/mixup of them.")
    print("-vc, --vict_cond <num>\tUses <num> to specify the number of sub-optimal mappings to encounter before terminating a thread,\n\t\t\tthat is, the victory condition. Default is 160, set to around 4000 to guarantee optimal mappings.")
    print("-so, --summary_only\tDoes not run the HWDSE, instead prints the results from a previously run (from the '/outputs_hwdse' folder).")
    print("-t, --table\t\tPrints a pretty-table of the summary after its textual form.")
    print("-i, --init_idx <idx>\tSets to <idx> the index of the first tried configuration, continuing from there. Default is 0.")
    print("-ih, --ignore_heads\tIgnores the fact that some layers are repeated once per head, considering them one time only.")
    print("-if, --imperfect_fact\tEnables imperfect factorization ('Ruby' version of Timeloop).")
    sys.exit(0)


### PARAMETERS DESCRIPTION:
# shared -> used both during matmuls and NOs
#'shared_glb_size': size of the on-chip SRAM buffer
# --> the above is measured in number-of-values-stored (hence, bytes since here data is in 8bits)
#'shared_glb_bandwidth': read and write network bandwidth for the scratchpad
# --> the above is measured in in words-per-cycle
## matmul only
#'pe_rows': rows of the spatial architecture
#'pe_cols': cols of the spatial architecture
#'dataflow': dataflow for the spatial architecture, one of "WS" or "IS"
## normop only
#'use_IMC_as_buffer': whether the IMC module can be used as a normal memory during NOs
# --> (since it has always proven counterproductive, it is not currently supported)
#'IMC_buffer_bandwidth': bandwidth of the IMC when used as memory
# --> (also not currently supported)
#'rf_size': size of a column vector processed during NOs
# --> the above is measured in number-of-values-stored (hence, bytes since here data is in 8bits)

hw_configs = [
    # 3 designs varying in SA rows/cols
    {
        # shared
        'shared_glb_size': 262144,
        'shared_glb_bandwidth': 16,
        # matmul only
        'pe_rows': 128,
        'pe_cols': 128,
        'dataflow': "WS",
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
        'IMC_buffer_bandwidth': 16,
        'rf_size': 1024
    }, {
        # shared
        'shared_glb_size': 262144,
        'shared_glb_bandwidth': 16,
        # matmul only
        'pe_rows': 64,
        'pe_cols': 256,
        'dataflow': "WS", #IS
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
        'IMC_buffer_bandwidth': 16,
        'rf_size': 1024
    }, {
        # shared
        'shared_glb_size': 262144,
        'shared_glb_bandwidth': 16,
        # matmul only
        'pe_rows': 256,
        'pe_cols': 64,
        'dataflow': "WS",
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
        'IMC_buffer_bandwidth': 16,
        'rf_size': 1024
    },
    # same 3 designs as above, with double on-chip memory and bandwidth
    {
        # shared
        'shared_glb_size': 262144*2,
        'shared_glb_bandwidth': 16*2,
        # matmul only
        'pe_rows': 128,
        'pe_cols': 128,
        'dataflow': "WS",
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
        'IMC_buffer_bandwidth': 16,
        'rf_size': 1024
    }, {
        # shared
        'shared_glb_size': 262144*2,
        'shared_glb_bandwidth': 16*2,
        # matmul only
        'pe_rows': 64,
        'pe_cols': 256,
        'dataflow': "WS", #IS
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
        'IMC_buffer_bandwidth': 16,
        'rf_size': 1024
    }, {
        # shared
        'shared_glb_size': 262144*2,
        'shared_glb_bandwidth': 16*2,
        # matmul only
        'pe_rows': 256,
        'pe_cols': 64,
        'dataflow': "WS",
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
        'IMC_buffer_bandwidth': 16,
        'rf_size': 1024
    }
]

results = []


def mixup_dicts(dicts):
    keys = dicts[0].keys()
    values = [list(set(d[key] for d in dicts)) for key in keys]
    seen = set()
    for combination in itertools.product(*values):
        new_dict = dict(zip(keys, combination))
        frozen_dict = frozenset(new_dict.items())
        if frozen_dict not in seen:
            seen.add(frozen_dict)
            yield new_dict

def pretty_format_dict(dictionary, level = 0):
    string = ""
    for key, value in (dictionary.items() if isinstance(dictionary, dict) else zip(["" for i in dictionary], dictionary)):
        string += "\t"*level + (f"{key}: " if key != "" else "- ")
        if isinstance(value, dict):
            string += "\n" + pretty_format_dict(value, level + 1)
        elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
            string += "\n" + pretty_format_dict(value, level + 1)
        else:
            string += str(value)
        string += "\n"
    return string.rstrip()

def append_to_file(path, text_to_append):
    with open(path, 'a') as file:
        file.write('\n\n' + text_to_append)

def recover_metrics(path, coefficient = 1):
    result = {}
    with open(os.path.join(path, "timeloop-mapper.stats.txt"), "r") as file:
        content = file.read()
        match = re.search(r"Energy: (\d+\.\d+) (\w+)", content)
        if match:
            energy_value = float(match.group(1))
            energy_unit = match.group(2)
            # NORMALIZE TO pJ
            if energy_unit == "mJ":
                factor = 10**9
            elif energy_unit == "uJ":
                factor = 10**6
            elif energy_unit == "nJ":
                factor = 10**3
            elif energy_unit == "pJ":
                factor = 10**0
            elif energy_unit == "fJ":
                factor = 10**-3
            result["energy"] = energy_value * factor * coefficient
        match = re.search(r"Cycles: (\d+)", content)
        if match:
            result["cycles"] = int(match.group(1)) * coefficient
        match = re.search(r"Utilization: (\d+.\d+)%", content)
        if match:
            result["utilization"] = float(match.group(1)) * coefficient
        match = re.search(r"EDP\(J\*cycle\): (\d+.\d+e[+-]\d+)", content)
        if match:
            result["edp"] = float(match.group(1)) * coefficient
    return result

def best_by_metric(results, metric, lower_is_better = True):
    best = math.inf if lower_is_better else 0
    configs = []
    for res in results:
        if (res['metrics'][metric] < best and lower_is_better) or (res['metrics'][metric] > best and not lower_is_better):
            best = res['metrics'][metric]
            configs = [res]
        elif res['metrics'][metric] == best:
            configs.append(res)
    return configs

def summary(results, msg = "RESULTS SUMMARY:", print_tested = False):
    print(f"\n\n{msg}\n")
    if print_tested:
        print("\n------> Tested configurations:\n" + "\n---\n".join(map(pretty_format_dict, results)))
        print("\n")
    print("\n---> Best by EDP-sum:\n" + "\n---\n".join(map(pretty_format_dict, best_by_metric(results, "edp"))))
    print("\n---> Best by ENERGY used:\n" + "\n---\n".join(map(pretty_format_dict, best_by_metric(results, "energy"))))
    print("\n---> Best by CYCLES used:\n" + "\n---\n".join(map(pretty_format_dict, best_by_metric(results, "cycles"))))
    print("\n---> Best by UTILIZATION used:\n" + "\n---\n".join(map(pretty_format_dict, best_by_metric(results, "utilization", False))))
    if options['table']:
        print("\n\nSUMMARY TABLE:")
        if len(results) > 0:
            references = {k : results[0][k] for k in hw_configs[0].keys() if k != 'metrics'}
            keep = []
            metrics = [k for k in results[0]['metrics'].keys()]
            for res in results[1:]:
                for k in [k for k in references.keys() if k not in keep]:
                    if res[k] != references[k]:
                        keep.append(k)
            table = PrettyTable(keep + metrics)
            for res in results:
                table.add_row([res[k] for k in keep] + [(res['metrics'][k] if isinstance(res['metrics'][k], int) else "{:.3f}".format(res['metrics'][k])) for k in metrics])
            print(table)
        else:
            print("NO RESULTS FOUND FROM PREVIOUS RUNS!\nEnsure that a folder called \"outputs_hwdse\" exists in the current directory.")

# Summary only, print it and quit
if options['summary_only']:
    for root, dirs, files in os.walk("./outputs_hwdse"):
        if "hw_config.json" in files:
            with open(os.path.join(root, "hw_config.json"), "r") as file:
                results.append(json.load(file))
    summary(results, print_tested = True)
    sys.exit(0)


matmuls = ["KQV", "KTQ", "VScores", "Out", "FF1", "FF2"]
normops = ["softmax", "layernorm"]
fusable = normops + ["KTQ", "Out"]
multihead = ["KTQ", "VScores", "softmax"]

valid_args_1 = matmuls + normops
desc_1 = [
    "First matmul, computes Q, K and V from Input with a projection.",
    "Second matmul, computes Scores as K^T*Q.",
    "Third matmul, computes V' with the convex combinations in V*Scores.",
    "Fourth matmul, computes Out from V' with a projection.",
    "Fifth matmul, first projection of the FF block, increases the latent dimension.",
    "Sixth matmul, second projection of the FF block, decreases back the latent dimension.",
    "Softmax operation, applied column-wise on the output of \"KTQ\".",
    "LayerNorm operation, applied column-wise on the output of \"Out\"."
]

# MUST STAY ORDERED! Set D,E=1 for all those above the specified one!
memory_levels = ["DRAM", "shared_glb", "scratchpad"]
desc_memory_levels = [
    "DRAM, off-chip storage, fusing here is the same as doing nothing XD.",
    "Global buffer, main on-chip SRAM storage, usual target for fusions.",
    "Scratchpad simulating the IMC SRAM, fusion possible iif all weights can fit it at once."
]

def arg_error():
    print("Error: Invalid argument(s).")
    print(f"Argvs: {sys.argv}")
    print("The first argument(s) must be either \"all\" or one or more of the following:\n- {}".format('\n- '.join([a + ': ' + d for a, d in zip(valid_args_1, desc_1)])))
    print("After the first argument(s) there can be the name of the memory hierarchy level at which to prepare for column-wise operation fusion, one of the following:\n- {}".format('\n- '.join([a + ': ' + d for a, d in zip(memory_levels, desc_memory_levels)])))
    sys.exit(1)

if len(sys.argv) < 2 or (sys.argv[1] not in valid_args_1 and sys.argv[1] != "all"):
    arg_error()

# Spill levels to run
target_ops = []
if sys.argv[1] == "all":
    target_ops = matmuls + normops
    sys.argv.pop(1)
else:
    while len(sys.argv) >= 2 and sys.argv[1] in matmuls + normops:
        target_ops.append(sys.argv.pop(1))

# Spill level at which to fuse
is_fusion = False
if len(sys.argv) > 2:
    arg_error()
elif len(sys.argv) == 2:
    if sys.argv[1] in memory_levels:
        is_fusion = True
    else:
        arg_error()

level_for_fusion = memory_levels.index(sys.argv[1]) if is_fusion else 0

print("Target operations:", target_ops)
print("Fusion set to:", is_fusion)
if is_fusion: print("Fusion enabled for level:", memory_levels[level_for_fusion])

constrained_factors = ["D=1"]
if not options['no_e_fusion']: constrained_factors.append("E=1")
if options['l_fusion']: constrained_factors.append("L=1")
constrained_factors = tl.constraints.Factors(constrained_factors)


idx = int(options['initial_idx']) if options['initial_idx'] else 0
for hw_config in (hw_configs if not options['mixup'] else mixup_dicts(hw_configs)):
    print(f"\n--------> Working on config: {idx}")
    print(pretty_format_dict(hw_config), end = "\n")

    total_layers = 0
    for layer in target_ops:
        print(f"\n----> Config {idx}, working on layer: {layer}\n")

        is_norm_op = layer in normops

        # Define relative paths
        ARCH_PATH = f"{os.curdir}/arch_v0.4/system_PIM{'_NOs' if is_norm_op else ''}.yaml"
        COMPONENTS_PATH = f"{os.curdir}/arch_v0.4/components/*.yaml"
        PROBLEM_PATH = f"{os.curdir}/layers/{layer}_layer.yaml"
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
        )

        # Setup the mapper
        spec.mapper.victory_condition = options['victory_condition'] if options['victory_condition'] else 160
        if options['live']:
            spec.mapper.live_status = True
        spec.mapspace.template = 'uber' if not options['imperfect_fact'] else 'ruby'

        # Setup the architecture
        WS_row_spatial_constr_factors = tl.constraints.Factors(["L=1", "E=1", f"D>={hw_config['pe_rows']//2}"])
        WS_row_temporal_constr_factors = tl.constraints.Factors(["D=1", "E=1"])
        WS_col_spatial_constr_factors = tl.constraints.Factors(["L=1", "D=1", f"E>={hw_config['pe_cols']//2}"])
        WS_col_temporal_constr_factors = tl.constraints.Factors(["D=1", "E=1"])
        IS_row_spatial_constr_factors = tl.constraints.Factors(["L=1", "D=1", f"E>={hw_config['pe_rows']//2}"])
        IS_row_temporal_constr_factors = tl.constraints.Factors(["L=1", "E=1"])
        IS_col_spatial_constr_factors = tl.constraints.Factors(["E=1", "D=1", f"L>={hw_config['pe_cols']//2}"])
        IS_col_temporal_constr_factors = tl.constraints.Factors(["L=1", "E=1"])

        buf = spec.architecture.find("shared_glb")
        buf.attributes["entries"] = hw_config['shared_glb_size']
        buf.attributes["depth"] = hw_config['shared_glb_size'] // (buf.attributes["width"] // buf.attributes["datawidth"])
        buf.attributes["read_bandwidth"] = hw_config['shared_glb_bandwidth']
        buf.attributes["write_bandwidth"] = hw_config['shared_glb_bandwidth']
        if not is_norm_op:
            pe_rows = spec.architecture.find("PERows")
            pe_rows.spatial.meshY = hw_config['pe_rows']
            pe_cols = spec.architecture.find("PECols")
            pe_cols.spatial.meshX = hw_config['pe_cols']
            sp = spec.architecture.find("scratchpad")
            sp.attributes["meshY"] = hw_config['pe_rows']
            sp.attributes["meshX"] = hw_config['pe_cols']
            mac = spec.architecture.find("mac")
            mac.attributes["meshY"] = hw_config['pe_rows']
            mac.attributes["meshX"] = hw_config['pe_cols']
            if hw_config['dataflow'] == "IS":
                pe_rows.constraints.spatial.factors = IS_row_spatial_constr_factors
                pe_rows.constraints.temporal.factors = IS_row_temporal_constr_factors
                pe_cols.constraints.spatial.factors = IS_col_spatial_constr_factors
                pe_cols.constraints.temporal.factors = IS_col_temporal_constr_factors
                for constr in spec.constraints['targets']:
                    if constr['target'] == "scratchpad" and constr['type'] == "dataspace":
                        constr['keep'].clear()
                        constr['keep'].append("Inputs")
                        constr['bypass'].clear()
                        constr['bypass'] += ["Weights", "Outputs"]
            elif hw_config['dataflow'] != "WS":
                print(f"------------> ERROR!! Invalid dataflow name: {hw_config['dataflow']}")
                sys.exit(1)
        else:
            in_reg = spec.architecture.find("Registers_Outputs")
            in_reg.attributes["depth"] = hw_config['rf_size']
            in_reg.attributes["entries"] = hw_config['rf_size']
            out_reg = spec.architecture.find("Registers_Inputs")
            out_reg.attributes["depth"] = hw_config['rf_size']
            out_reg.attributes["entries"] = hw_config['rf_size']
            IMC_buf = spec.architecture.find("IMC_as_buffer")
            IMC_buf.attributes["read_bandwidth"] = hw_config['IMC_buffer_bandwidth']
            IMC_buf.attributes["write_bandwidth"] = hw_config['IMC_buffer_bandwidth']
            for constr in spec.constraints['targets']:
                # Fix maximize_dims
                if constr['target'] == "shared_glb" and 'maximize_dims_capacity' in constr:
                    constr['maximize_dims_capacity'] = buf.attributes["entries"] // (hw_config['rf_size']*2)
                if constr['target'] == "Registers_Inputs" and constr['type'] == "temporal":
                    constr['factors'] = tl.constraints.Factors([f"E={hw_config['rf_size']}", "L=1"])
            if hw_config['use_IMC_as_buffer']:
                print("WARNING: \"use_IMC_as_buffer\" has not yet been implemented!")

        # Setup fusion constraints
        if spec.constraints['targets'] is None:
            spec.constraints['targets'] = tl.constraints.ConstraintsList()
        if is_fusion and layer in fusable:
            if not is_norm_op:
                # Apply fusion constraints
                found = []
                for target in spec.constraints['targets']:
                    if target['target'] in memory_levels[0:level_for_fusion] and target['target'] not in found and target.type == "temporal":
                        found.append(target['target'])
                        target.factors = constrained_factors
                        print(f"Updating constraint (factors): {dict(target.items())}")
                for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion])):
                    spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': target, 'type': 'temporal', 'factors': constrained_factors}))
                    print(f"Adding constraint (factors): {dict(spec.constraints['targets'][-1].items())}")
                found.clear()

                if not options['pay_writeback_in_matmul']:
                    for target in spec.constraints['targets']:
                        if target['target'] in memory_levels[0:level_for_fusion] and target['target'] and target['type'] == "dataspace":
                            found.append(target['target'])
                            # The cost of writing back outputs in in the NOs!
                            if "Outputs" not in target['bypass']:
                                target.bypass.append("Outputs")
                            if "Outputs" in target['keep']:
                                target.keep.remove("Outputs")
                            print(f"Updating constraint (bypasses): {dict(target.items())}")
                    for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion])):
                        spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': target, 'type': 'dataspace', 'bypass': ["Outputs"], 'keep': ["Inputs", "Weights"]}))
                        print(f"Adding constraint (bypasses): {dict(spec.constraints['targets'][-1].items())}")
                    found.clear()
            
                # THE LEVEL AT WHICH YOU FUSE MUST HAVE LOOPS (inner)EDL(outer)
                for target in spec.constraints['targets']:
                    if target['target'] in memory_levels[0:level_for_fusion+1] and target['target'] and target['type'] == "temporal":
                        found.append(target['target'])
                        target['permutation'] = tl.constraints.Permutation(['E', 'D', 'L'])
                        print(f"Updating constraint (permutation): {dict(target.items())}")
                        break
                for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion+1])):
                    spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': memory_levels[level_for_fusion], 'type': 'temporal', 'permutation': ['E', 'D', 'L']}))
                    print(f"Adding constraint (permutation): {dict(spec.constraints['targets'][-1].items())}")
            
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
                        if options['pay_writeback_in_matmul']:
                            if "Outputs" not in target['bypass']:
                                target.bypass.append("Outputs")
                            if "Outputs" in target['keep']:
                                target.keep.remove("Outputs")
                        print(f"Updating constraint (bypasses): {dict(target.items())}")
                for target in list(filter(lambda x : x not in found, memory_levels[0:level_for_fusion])):
                    spec.constraints['targets'].append(tl.constraints.constraint_factory({'target': target, 'type': 'dataspace', 'bypass': ["Inputs", "Weights", "Outputs"] if options['pay_writeback_in_matmul'] else ["Inputs", "Weights"]}))
                    print(f"Adding constraint (bypasses): {dict(spec.constraints['targets'][-1].items())}")

        # Run the Timeloop mapper
        output_dir = f"{os.curdir}/outputs_hwdse/{idx}/outputs_{layer}" + (("_" + sys.argv[2]) if level_for_fusion else "")
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        tl.call_mapper(spec, output_dir=output_dir)
        
        # Collect results
        append_to_file(f"{output_dir}/timeloop-mapper.map.txt", f"Fusion optimized: {is_fusion}\nFusion constraints: {constrained_factors}")
        append_to_file(f"{output_dir}/timeloop-mapper.map.txt", f"Hardware Configuration: {pretty_format_dict(hw_config)}")
        try:
            metrics = recover_metrics(output_dir, spec.variables['HEADS'] if layer in multihead and not options['ignore_heads'] else 1)
        except:
            print(f"\n\n------------> ERROR!! Mapping failed for layer ->{layer}<- on config:\n{pretty_format_dict(hw_config)}")
            print("Assuming metrics = +inf or 0 depending on the case...\n")
            metrics = {
                'energy': math.inf,
                'cycles': math.inf,
                'utilization': 0,
                'edp': math.inf
            }
        append_to_file(f"{output_dir}/timeloop-mapper.map.txt", f"Relevant Metrics: {pretty_format_dict(metrics)}")

        if 'metrics' not in hw_config:
            hw_config['metrics'] = metrics
        else:
            for k in metrics.keys():
                hw_config['metrics'][k] += metrics[k]

        total_layers += spec.variables['HEADS'] if layer in multihead and not options['ignore_heads'] else 1

    hw_config['metrics']['utilization'] /= total_layers

    output_dir = f"{os.curdir}/outputs_hwdse/{idx}"
    with open(f"{output_dir}/hw_config.json", 'w') as file:
        file.write(json.dumps(hw_config, indent = 1))
    
    results.append(hw_config)
    idx += 1

def best_by_metric(results, metric, lower_is_better = True):
    best = math.inf if lower_is_better else 0
    configs = []
    for res in results:
        if (res['metrics'][metric] < best and lower_is_better) or (res['metrics'][metric] > best and not lower_is_better):
            best = res['metrics'][metric]
            configs = [res]
        elif res['metrics'][metric] == best:
            configs.append(res)
    return configs

summary(results, "Exploration terminated! Searching for best configuration...")