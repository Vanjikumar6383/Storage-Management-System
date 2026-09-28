"""
Realistic Storage Lifecycle Benchmark Dataset Generator
Designed for Multi-Tenant Cloud Environments & Short-Lived Development Infrastructure.
"""

from pathlib import Path
import sys

# Re-use generation logic
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

import importlib.util
spec = importlib.util.spec_from_file_location("dataset_gen", str(root_dir / "import random.py"))
gen_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_mod)

if __name__ == "__main__":
    out_file = str(root_dir / "Data" / "storage_lifecycle_dataset_cleaned.csv")
    data = gen_mod.generate_realistic_dataset(num_objects=10000, seed=42)
    gen_mod.save_dataset_to_csv(data, out_file)
    gen_mod.print_dataset_summary(data)
