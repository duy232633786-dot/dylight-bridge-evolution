from bridge_evolution.pareto import dominates, ParetoArchive, hypervolume_2d


def test_dominates():
    assert dominates((1, 1), (2, 2))
    assert dominates((1, 2), (2, 2))
    assert not dominates((1, 3), (2, 2))
    assert not dominates((2, 2), (2, 2))


def test_archive_keeps_only_nondominated():
    a = ParetoArchive()
    assert a.add("x", (2.0, 2.0))
    assert a.add("y", (1.0, 3.0))
    assert not a.add("z", (3.0, 3.0))       # bị (2,2) trội
    assert a.add("w", (1.5, 1.5))            # trội (2,2) → loại nó
    fronts = set(a.front)
    assert (2.0, 2.0) not in fronts and len(fronts) == 2


def test_hypervolume_2d():
    # 1 điểm (1,1), ref (3,3): HV = 2×2 = 4
    assert abs(hypervolume_2d([(1.0, 1.0)], (3.0, 3.0)) - 4.0) < 1e-9
    # thêm điểm bị trội không đổi HV
    assert abs(hypervolume_2d([(1.0, 1.0), (2.0, 2.0)], (3.0, 3.0)) - 4.0) < 1e-9
    # điểm ngoài ref không đóng góp
    assert hypervolume_2d([(4.0, 4.0)], (3.0, 3.0)) == 0.0
