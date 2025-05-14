from challenge_cli.core.data_utils import compare_results, parse_cases_arg


def test_parse_cases_arg():
    assert parse_cases_arg("1,3,5-7", 10) == {1, 3, 5, 6, 7}
    assert parse_cases_arg(None, 5) == {1, 2, 3, 4, 5}
    assert parse_cases_arg("1-3", 10) == {1, 2, 3}


def test_compare_results():
    assert compare_results([1, 2], [2, 1])
    assert compare_results({"a": 1}, {"a": 1})
    assert compare_results("hello", "hello")
