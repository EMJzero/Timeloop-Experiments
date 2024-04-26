import timeloopfe.v4 as tl
import itertools
import signal
import code
import math
import time
import json
import sys
import os
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
        "mixup": if_match_and_remove("-mx") or if_match_and_remove("--mixup")
    }
    return options

print(f"Arguments provided: {sys.argv}")
options = parse_options()

if options['help']:
    print("Available options:")
    print("-h, --help\t\tPrint this help menu.")
    print("-l, --live\t\tShow Timeloop's live status as it runs.")
    print("-nef, --no_e_fusion\tDo not enforce E=1 when doing fusions (useful only on matmul layers).")
    print("\t\t\t[Increases the latency with which column vectors are ready, due to DRAM accesses]")
    print("-lf, --l_fusion\t\tEnforce L=1 when doing fusions (useful only on matmul layers).")
    print("\t\t\t[Stores the entirety of the output in the Accumulator, useful NO execution\n\t\t\tdoes not overlap with the matmul, but happens later]")
    print("-pwim, --pay_wb_in_mm\tWhen fusing, moves estimation of the cost of writing the final output from the NOs to the matmul.")
    print("\t\t\t[Essentially, now the matmul writes to DRAM, and the NO simply operates to and from on-chip memories]")
    print("-mx, --mixup\t\tInstead of trying only hardcoded hardware configurations, also try any permutation/mixup of them.")
    sys.exit(0)

hw_configs = [
    {
        # shared
        'shared_glb_size': 262144,
        # matmul only
        'pe_rows': 128,
        'pe_cols': 128,
        'dataflow': "WS",
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
        'rf_size': 1024
    }, {
        # shared
        'shared_glb_size': 262144*4,
        # matmul only
        'pe_rows': 128,
        'pe_cols': 128,
        'dataflow': "IS",
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
        'rf_size': 1024
    }, {
        # shared
        'shared_glb_size': 262144*2,
        # matmul only
        'pe_rows': 256,
        'pe_cols': 64,
        'dataflow': "WS",
        # normop only
        'use_IMC_as_buffer': False, # infer IMC buffer size from pe cols/rows
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

def recover_metrics(path):
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
            result["energy"] = energy_value * factor
        match = re.search(r"Cycles: (\d+)", content)
        if match:
            cycles = int(match.group(1))
            result["cycles"] = cycles
        match = re.search(r"Utilization: (\d+.\d+)%", content)
        if match:
            utilization = float(match.group(1))
            result["utilization"] = utilization
    return result

matmuls = ["KQV", "KTQ", "VScores", "Out", "FF1", "FF2"]
normops = ["softmax", "layernorm"]
fusable = normops + ["KTQ", "Out"]

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

WS_row_spatial_constr_factors = tl.constraints.Factors(["L=1", "E=1", "D>=32"])
WS_row_temporal_constr_factors = tl.constraints.Factors(["D=1", "E=1"])
WS_col_spatial_constr_factors = tl.constraints.Factors(["L=1", "D=1", "E>=32"])
WS_col_temporal_constr_factors = tl.constraints.Factors(["D=1", "E=1"])
IS_row_spatial_constr_factors = tl.constraints.Factors(["L=1", "D=1", "E>=32"])
IS_row_temporal_constr_factors = tl.constraints.Factors(["L=1", "E=1"])
IS_col_spatial_constr_factors = tl.constraints.Factors(["E=1", "D=1", "L>=32"])
IS_col_temporal_constr_factors = tl.constraints.Factors(["L=1", "E=1"])


idx = 0
for hw_config in (hw_configs if not options['mixup'] else mixup_dicts(hw_configs)):
    idx += 1
    print(f"\n--------> Working on config: {idx}")
    print(pretty_format_dict(hw_config), end = "\n")

    for layer in target_ops:
        print(f"\n----> Working on layer: {layer}\n")

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
        spec.mapper.victory_condition = 160#0
        if options['live']:
            spec.mapper.live_status = True
        spec.mapspace.template = 'uber' #'ruby'

        # Setup the architecture
        buf = spec.architecture.find("shared_glb")
        buf.attributes["entries"] = hw_config['shared_glb_size']
        buf.attributes["depth"] = hw_config['shared_glb_size'] // (buf.attributes["width"] // buf.attributes["datawidth"])
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
            elif hw_config['dataflow'] != "WS":
                print(f"Invalid dataflow name: {hw_config['dataflow']}")
                sys.exit(1)
        else:
            in_reg = spec.architecture.find("Registers_Outputs")
            in_reg.attributes["depth"] = hw_config['rf_size']
            in_reg.attributes["entries"] = hw_config['rf_size']
            out_reg = spec.architecture.find("Registers_Inputs")
            out_reg.attributes["depth"] = hw_config['rf_size']
            out_reg.attributes["entries"] = hw_config['rf_size']
            if hw_config['use_IMC_as_buffer']:
                print("WARNING: \"use_IMC_as_buffer\" has not yet been implemented!")

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

        output_dir = f"{os.curdir}/outputs_hwdse/{idx}/outputs_{layer}" + (("_" + sys.argv[2]) if level_for_fusion else "")
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        tl.call_mapper(spec, output_dir=output_dir)  # Run the Timeloop mapper
        
        append_to_file(f"{output_dir}/timeloop-mapper.map.txt", f"Fusion optimized: {is_fusion}\nFusion constraints: {constrained_factors}")
        append_to_file(f"{output_dir}/timeloop-mapper.map.txt", f"Hardware Configuration: {pretty_format_dict(hw_config)}")
        metrics = recover_metrics(output_dir)
        append_to_file(f"{output_dir}/timeloop-mapper.map.txt", f"Relevant Metrics: {pretty_format_dict(metrics)}")

        if 'metrics' not in hw_config:
            hw_config['metrics'] = metrics
        else:
            for k in metrics.keys():
                hw_config['metrics'][k] += metrics[k]

    with open(f"{output_dir}/hw_config.json", 'w') as file:
        file.write(json.dumps(hw_config, indent = 1))
    
    results.append(hw_config)

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

print("\n\nExploration terminated! Searching for best configuration...\n")
print("\nBest by ENERGY used:\n" + "\n---\n".join(map(pretty_format_dict, best_by_metric(results, "energy"))))
print("\nBest by CYCLES used:\n" + "\n---\n".join(map(pretty_format_dict, best_by_metric(results, "cycles"))))
print("\nBest by UTILIZATION used:\n" + "\n---\n".join(map(pretty_format_dict, best_by_metric(results, "utilization", False))))