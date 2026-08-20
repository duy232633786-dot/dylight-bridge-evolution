from experiments.compare_to_oracle import additive_epsilon, compare, igd_plus


def _item(case_id, point):
    keys = ("relative_cost", "material_mass_t", "embodied_carbon_kgCO2e")
    return {"case_id": case_id, "objectives": dict(zip(keys, point))}


def test_oracle_metrics_are_zero_for_exact_front():
    front = [_item("a", (2000, 500, 90000)),
             _item("b", (2100, 480, 88000))]
    result = compare(front, front)
    assert result["exact_oracle_front"] is True
    assert result["oracle_recall"] == 1.0
    assert result["best_cost_gap_pct"] == 0.0
    assert result["igd_plus_normalized"] == 0.0
    assert result["epsilon_additive_normalized"] == 0.0
    assert result["hv_2d_ratio"] == 1.0
    assert result["hv_3d_ratio"] == 1.0


def test_missing_tradeoff_point_has_positive_distance():
    reference = [(2000, 500, 90000), (2100, 450, 85000)]
    approximation = [reference[0]]
    assert igd_plus(reference, approximation) > 0
    assert additive_epsilon(reference, approximation) > 0
