"""Fallback runner when pytest isn't installed:  python run_tests.py"""
import importlib, pathlib, sys, traceback
sys.path.insert(0, str(pathlib.Path(__file__).parent))
passed = failed = 0
for f in sorted(pathlib.Path("tests").glob("test_*.py")):
    mod = importlib.import_module(f"tests.{f.stem}")
    for name in dir(mod):
        if name.startswith("test_"):
            try:
                getattr(mod, name)(); passed += 1; print("PASS", f.stem, name)
            except Exception:
                failed += 1; print("FAIL", f.stem, name); traceback.print_exc()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
