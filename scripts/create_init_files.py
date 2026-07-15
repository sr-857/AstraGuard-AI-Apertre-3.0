import os

def find_missing_init_files(root_dir):
    missing_dirs = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if '__pycache__' in dirpath:
            continue
        init_file = os.path.join(dirpath, '__init__.py')
        if not os.path.exists(init_file):
            missing_dirs.append(dirpath)
    return missing_dirs

def create_init_files(root_dir):
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if '__pycache__' in dirpath:
            continue
        init_file = os.path.join(dirpath, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write('')
            print(f"Created {init_file}")

if __name__ == "__main__":
    missing = find_missing_init_files('src')
    if missing:
        print("Missing __init__.py files in:")
        for d in missing:
            print(f"  {d}")
        print("\nCreating missing __init__.py files...")
        create_init_files('src')
    else:
        print("All directories already have __init__.py files.")
