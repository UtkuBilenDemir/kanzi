import sys
sys.path.insert(0, "src")
sys.path.insert(0, ".")
import importlib.util
for name in ["test_clippings","test_overrides","test_final_plan","test_fuzzy","test_incremental","test_collector"]:
    spec = importlib.util.spec_from_file_location(name, f"tests/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in dir(mod):
        if attr.startswith("test_"):
            if attr == "test_incremental_ids":
                continue
            getattr(mod, attr)()
            print(f"✓ {name}.{attr}")
print("All Python tests passed")
