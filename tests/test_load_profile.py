from sim.load_profile import LoadProfile


def test_load_profile_reads_normalized_values(tmp_path):
    path = tmp_path / "profile.csv"
    path.write_text(
        "timestamp,current_demand_mw\n"
        "2024-01-01T00:00:00,100\n"
        "2024-01-01T00:05:00,200\n",
        encoding="utf-8",
    )
    profile = LoadProfile.from_csv(str(path))
    assert profile.value_at_minute(0) == 100
    assert profile.value_at_minute(5) == 200
    assert profile.normalized_at_minute(5) == 1
