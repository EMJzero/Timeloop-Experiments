import timeloopfe.v4 as tl
import os
import shutil
import matplotlib.pyplot as plt
import joblib

TOP_PATH = f"{os.curdir}/top.yaml.jinja"

def run_test(global_buffer_size_scale: float, pe_scale: float, brief_print: bool=False):
    if brief_print:
        print('.', end='')
    # Set up the specification
    spec = tl.Specification.from_yaml_files(TOP_PATH)
    buf = spec.architecture.find("buffer")
    buf.attributes["depth"] = round(buf.attributes["depth"] * global_buffer_size_scale)
    pe = spec.architecture.find("PE")
    pe.spatial.meshX = round(pe.spatial.meshX * pe_scale)
    spec.mapper.search_size = 2000

    # Give each run a unique ID and run the mapper
    proc_id = f"glb_scale={global_buffer_size_scale},pe_scale={pe_scale}"
    if brief_print:
        print('.', end='')
    else:
        print(f"Starting {proc_id}")
    out_dir = f"{os.curdir}/outputs/{proc_id}"
    ret = tl.call_mapper(spec, output_dir=out_dir, log_to=f"{out_dir}/output.log")
    print(f"Done {proc_id} {ret}")

    # Grab the energy from the stats file
    stats = open(f"{out_dir}/timeloop-mapper.stats.txt").read()
    stats = [l.strip() for l in stats.split("\n") if l.strip()]
    energy = float(stats[-1].split("=")[-1])
    return (
        spec.architecture.find("buffer").attributes["depth"],
        spec.architecture.find("PE").spatial.meshX,
        energy,
    )

args = []
results = []
for global_buffer_size_scale in [0.5, 1, 2]:
    for n_pes in [0.5, 1, 2]:
        arg = (global_buffer_size_scale, n_pes)
        args.append(arg)

# Slow non-multi-processed implementation
# for arg in args:
#   results.append(run_test(*arg))

# Fast multiprocessed implementation

results = joblib.Parallel(n_jobs=16)(
    joblib.delayed(run_test)(*arg) for arg in args
)

for global_buffer_depth, n_pes, energy in results:
    print(
        f"Global buffer depth: {global_buffer_depth}, # PEs: {n_pes}, pJ/MAC: {energy}"
    )

args = []
for step in range(1, 41):
    global_buffer_size_scale = step / 10
    args.append((global_buffer_size_scale, 1, True))

results = joblib.Parallel(n_jobs=20)(
    joblib.delayed(run_test)(*arg) for arg in args
)

buffer_depths = [r[0] for r in results]
energies = [r[2] for r in results]

plt.plot(buffer_depths, energies)
plt.xlabel('Buffer Depth (Words)')
plt.ylabel('Energy (pJ/MAC)')
plt.title('Energy vs Buffer Depth')
plt.savefig('dse.png', bbox_inches='tight')

shutil.rmtree(f"{os.curdir}/outputs")
