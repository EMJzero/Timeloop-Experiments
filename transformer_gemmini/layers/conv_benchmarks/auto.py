import os
import re
import shutil

def update_files(benchmark_convs, template_filename):
    # Read the template file contents
    with open(template_filename, 'r') as file:
        template_content = file.read()
    
    # Iterate through the dictionary entries
    for key, values in benchmark_convs.items():
        new_content = template_content
        for param, new_value in values.items():
            # Replace the value in the template
            new_content = re.sub(rf'({param}:)\s*\d+', rf'\1 {new_value}', new_content)
        
        # Create new file with the dictionary key as name
        new_filename = f"{key}.yaml"
        with open(new_filename, 'w') as new_file:
            new_file.write(new_content)
        
        print(f"Created file: {new_filename}")

# Example dictionary
benchmark_convs = {
    # VGG16
    'I': dict(E = 128, D = 256, L = 56, Q = 56, R = 3, S = 3, Hstride = 1, Wstride = 1, Hdilation = 1, Wdilation = 1),
    'II': dict(E = 512, D = 512, L = 28, Q = 28, R = 3, S = 3, Hstride = 1, Wstride = 1, Hdilation = 1, Wdilation = 1),
    # ResNet18 and 50
    'III': dict(E = 3, D = 64, L = 112, Q = 112, R = 7, S = 7, Hstride = 2, Wstride = 2, Hdilation = 1, Wdilation = 1),
    'IV': dict(E = 64, D = 64, L = 56, Q = 56, R = 3, S = 3, Hstride = 1, Wstride = 1, Hdilation = 1, Wdilation = 1),
    'V': dict(E = 128, D = 128, L = 28, Q = 28, R = 3, S = 3, Hstride = 1, Wstride = 1, Hdilation = 1, Wdilation = 1),
    'VI': dict(E = 256, D = 256, L = 14, Q = 14, R = 3, S = 3, Hstride = 1, Wstride = 1, Hdilation = 1, Wdilation = 1),
    'VII': dict(E = 256, D = 512, L = 7, Q = 7, R = 3, S = 3, Hstride = 2, Wstride = 2, Hdilation = 1, Wdilation = 1),
    'VIII': dict(E = 64, D = 256, L = 56, Q = 56, R = 1, S = 1, Hstride = 1, Wstride = 1, Hdilation = 1, Wdilation = 1), # depth-wise
    # MobileNetV3
    'IX': dict(E = 3, D = 64, L = 112, Q = 112, R = 3, S = 3, Hstride = 2, Wstride = 2, Hdilation = 1, Wdilation = 1),
    'X': dict(E = 72, D = 72, L = 28, Q = 28, R = 3, S = 3, Hstride = 2, Wstride = 2, Hdilation = 1, Wdilation = 1),
    'XI': dict(E = 576, D = 576, L = 7, Q = 7, R = 5, S = 5, Hstride = 1, Wstride = 1, Hdilation = 1, Wdilation = 1),
    'XII': dict(E = 24, D = 88, L = 28, Q = 28, R = 1, S = 1, Hstride = 1, Wstride = 1, Hdilation = 1, Wdilation = 1), # depth-wise
    # Strides and Dilation
    'XIII': dict(E = 16, D = 16, L = 224, Q = 224, R = 3, S = 3, Hstride = 3, Wstride = 3, Hdilation = 4, Wdilation = 4),
    'XIV': dict(E = 128, D = 128, L = 112, Q = 112, R = 9, S = 9, Hstride = 4, Wstride = 4, Hdilation = 3, Wdilation = 3),
    'XV': dict(E = 256, D = 256, L = 56, Q = 56, R = 3, S = 3, Hstride = 2, Wstride = 2, Hdilation = 3, Wdilation = 3)
}

template_filename = "template.txt"
update_files(benchmark_convs, template_filename)
