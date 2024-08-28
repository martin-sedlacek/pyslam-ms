import os
import numpy as np

def process_pose_matrix(matrix, prev_pos):
    """Extract x, y, z, and scale from the 4x4 pose matrix."""
    x = matrix[0, 3]
    y = matrix[1, 3]
    z = matrix[2, 3]
    scale = 1.0 if not prev_pos else np.linalg.norm(np.array((x, y, z)) - np.array(prev_pos))
    return x, y, z, scale

def read_matrix_from_file(file_path):
    """Read a 4x4 pose matrix from a text file."""
    with open(file_path, 'r') as f:
        matrix = []
        for line in f:
            matrix.append([float(num) for num in line.strip().split()])
        return np.array(matrix)

def process_all_files(input_folder, output_file_path):
    """Process all text files in the input folder and write the results to an output file."""
    files = sorted(os.listdir(input_folder), key=lambda x: int(x.split('.')[0]))  # Sort files by name as number

    with open(output_file_path, 'w') as output_file:
        prev_pos = None
        for file_name in files:
            file_number = int(file_name.split('.')[0])
            print(file_number)
            if file_number > 99:
                break
            file_path = os.path.join(input_folder, file_name)
            matrix = read_matrix_from_file(file_path)
            x, y, z, scale = process_pose_matrix(matrix, prev_pos)
            prev_pos = (x, y, z)
            output_file.write(f"{x} {y} {z} {scale}\n")
            print(f"Processed {file_name}: x={x}, y={y}, z={z}, scale={scale}")

# Set the input and output paths
input_folder = "/home/vy/datasets/scannet/scans/scene0000_00/pose"
output_file_path = "/home/vy/datasets/scannet/scans/scene0000_00/tmp_img_martin/ground_truth.txt"

# Process the files
process_all_files(input_folder, output_file_path)
