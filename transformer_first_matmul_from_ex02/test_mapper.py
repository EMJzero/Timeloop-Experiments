# Set up imports
import os
import timeloopfe.v4 as tl

# Define relative paths
ARCH_PATH = f"{os.curdir}/inputs/arch.yaml"
COMPONENTS_PATH = f"{os.curdir}/inputs/components.yaml"
PROBLEM_PATH = f"{os.curdir}/inputs/problem.yaml"
MAPPER_PATH = f"{os.curdir}/inputs/mapper.yaml"
VARIABLES_PATH = f"{os.curdir}/inputs/variables.yaml"
TOP_PATH = f"{os.curdir}/top.yaml.jinja"

spec = tl.Specification.from_yaml_files(
    ARCH_PATH,
    COMPONENTS_PATH,
    MAPPER_PATH,
    PROBLEM_PATH,
    VARIABLES_PATH,
)  # Gather YAML files into a Python object
tl.call_mapper(spec, output_dir=f"{os.curdir}/outputs")  # Run the Timeloop mapper
stats = open("outputs/timeloop-mapper.stats.txt").read()
print(stats[stats.index("Summary Stats") :])

def read_and_indent(path, n_lines=30, start_at: str = None, end_at: str = None):
    content = open(path).read()
    if start_at is not None:
        content = content[content.index(start_at) :]
    if end_at is not None:
        content = content[: content.index(end_at) + len(end_at)]
    content = content.split("\n")
    content = content[:n_lines] if n_lines > 0 else content[n_lines:]
    return "\t" + "\n\t".join(content)


print(f"Mapping:")
print(read_and_indent("outputs/timeloop-mapper.map.txt"))

#print(f"Accelergy log:")
#print(read_and_indent("outputs/timeloop-mapper.accelergy.log", -60))

#print(f"Energy reference table:")
#print(read_and_indent("outputs/timeloop-mapper.ERT.yaml"))

#print(f"Area reference table:")
#print(read_and_indent("outputs/timeloop-mapper.ART.yaml"))

tl.call_accelergy_verbose(
    spec,
    output_dir=f"{os.curdir}/outputs",
    log_to=f"{os.curdir}/outputs/accelergy_verbose.log",
)
#print(f"Verbose Accelergy log:")
#print(read_and_indent("outputs/accelergy_verbose.log", -60))

#print(f"Verbose energy reference table:")
#print(read_and_indent("outputs/ERT.yaml"))

#print(f"Verbose area reference table:")
#print(read_and_indent("outputs/ART.yaml"))

