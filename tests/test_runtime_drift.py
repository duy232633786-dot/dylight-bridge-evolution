import importlib.util, pathlib, sys
_p = pathlib.Path(__file__).resolve().parent.parent / "docs" / "check_runtime_drift.py"
_s = importlib.util.spec_from_file_location("check_runtime_drift", _p)
_m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)

def test_docs_do_not_drift_from_runtime():
    assert _m.run_all_checks() == []
