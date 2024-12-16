import os
import re

def extract_data_from_file(file_path):
    data = {}
    with open(file_path, 'r') as file:
        content = file.read()
        energy_match = re.search(r'Energy:\s*([\d.eE+-]+)\s*uJ', content)
        cycles_match = re.search(r'Cycles:\s*([\d.eE+-]+)', content)
        edp_match = re.search(r'EDP\(J\*cycle\):\s*([\d.eE+-]+)', content)
        time_match = re.search(r'time:\s*([\d.eE+-]+)', content)
        
        data['Energy (uJ)'] = float(energy_match.group(1)) if energy_match else 'N/A'
        data['Cycles'] = int(cycles_match.group(1)) if cycles_match else 'N/A'
        data['EDP (J*cycle)'] = float(edp_match.group(1)) if edp_match else 'N/A'
        data['MSE Runtime (s)'] = float(time_match.group(1)) if time_match else 'N/A'
        
    return data

def format_value(value, format_type):
    if value == 'N/A':
        return value
    if format_type == 'exp':
        return f"{value:.2e}"
    elif format_type == 'float':
        return f"{value:.2f}"
    return value

def print_table(rows, pretty_table = False):
    if pretty_table:
        from prettytable import PrettyTable
        table = PrettyTable(["Comp", "Arch", "EDP (J*cycle)", "Cycles", "Energy (uJ)", "MSE Runtime (s)"])
        for row in rows:
            table.add_row([
                row['Comp'],
                row['Arch'],
                format_value(row['EDP (J*cycle)'], 'exp'),
                str(row['Cycles']),
                format_value(row['Energy (uJ)'], 'float'),
                format_value(row['MSE Runtime (s)'], 'float')
            ])
        print(table)
        return

    header = "| Comp | Arch | Mapper | EDP (J*cycle) | Cycles | Energy (uJ) | MSE Runtime (s) |"
    separator = "| --- | --- | --- | --- | --- | --- | --- |"
    print(header)
    print(separator)
    
    for row in rows:
        formatted_row = [
            row['Comp'],
            row['Arch'],
            'TL',
            format_value(row['EDP (J*cycle)'], 'exp'),
            str(row['Cycles']),
            format_value(row['Energy (uJ)'], 'float'),
            format_value(row['MSE Runtime (s)'], 'float')
        ]
        print("| " + " | ".join(formatted_row) + " |")

def main(root_path, file_name):
    rows = []

    for subdir, _, files in os.walk(root_path):
        if file_name in files:
            arch_comp = os.path.basename(subdir)
            if "_" in arch_comp:
                arch, comp = arch_comp.split("_", 1)
            else:
                continue
            
            file_path = os.path.join(subdir, file_name)
            file_data = extract_data_from_file(file_path)
            
            row = {
                'Comp': comp,
                'Arch': arch,
                'Mapper': 'TL',
                'EDP (J*cycle)': file_data['EDP (J*cycle)'],
                'Cycles': file_data['Cycles'],
                'Energy (uJ)': file_data['Energy (uJ)'],
                'MSE Runtime (s)': file_data['MSE Runtime (s)']
            }
            rows.append(row)
    
    print_table(rows)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate a markdown table from log files.")
    parser.add_argument("path", help="The root directory containing the subdirectories.")
    parser.add_argument("file_name", help="The name of the file to search for in subdirectories.")
    
    args = parser.parse_args()
    
    main(args.path, args.file_name)
