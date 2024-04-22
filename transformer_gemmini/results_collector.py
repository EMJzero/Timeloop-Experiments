import os
import re

def extract_energy_stats():
    # Initialize the result dictionary
    result = {}

    # Walk through the current directory
    for root, dirs, files in os.walk("."):
        # If the directory name starts with "outputs"
        if root.startswith("./outputs"):
            # If "stats.txt" is in the files of the directory
            if "timeloop-mapper.stats.txt" in files:
                # Open the "stats.txt" file
                with open(os.path.join(root, "timeloop-mapper.stats.txt"), "r") as file:
                    # Read the file content
                    result[root] = {}
                    content = file.read()

                    # Search for the line like "Energy: 48.64 uJ"
                    match = re.search(r"Energy: (\d+\.\d+) (\w+)", content)
                    # If the line is found
                    if match:
                        # Store the "48.64" and "uJ" in two variables
                        energy_value = float(match.group(1))
                        energy_unit = match.group(2)
                        # Add the folder name and the results of the search to the dictionary
                        result[root]["energy"] = energy_value
                        result[root]["energy_unit"] = energy_unit

                    # Search for the line like "Cycles: 65536"
                    match = re.search(r"Cycles: (\d+)", content)
                    # If the line is found
                    if match:
                        # Store the "65536" in a variables
                        cycles = int(match.group(1))
                        # Add the folder name and the results of the search to the dictionary
                        result[root]["cycles"] = cycles

                    # Search for the line like "Utilization: 100.00%"
                    match = re.search(r"Utilization: (\d+.\d+)%", content)
                    # If the line is found
                    if match:
                        # Store the "100.00" in a variables
                        utilization = float(match.group(1))
                        # Add the folder name and the results of the search to the dictionary
                        result[root]["utilization"] = utilization

    # Return the result dictionary
    return result

def pretty_print_dict(dictionary):
    # Manually pretty print the dictionary
    for key, value in dictionary.items():
        print(f"{key}:")
        for sub_key, sub_value in value.items():
            print(f"{sub_key}: {sub_value}", end="\t\t")
        print("")

# Call the function and pretty print the results
pretty_print_dict(extract_energy_stats())
