from challenge_cli.core.formatting import format_memory, format_time


def test_format_time():
    assert format_time(0.0000001) == "100.00 ns"
    assert format_time(0.0001) == "100.00 μs"
    assert format_time(0.1) == "100.00 ms"
    assert format_time(10) == "10.000000 s"


def test_format_memory():
    assert format_memory(500) == "500.00 B"
    assert format_memory(1024) == "1.00 KB"
    assert format_memory(1048576) == "1.00 MB"
