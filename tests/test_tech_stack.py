import tech_stack


def test_mentioned_languages_detects_python_and_sql():
    assert tech_stack.mentioned_languages("Wrote a python script using sql queries") == {
        "Python",
        "SQL",
    }


def test_mentioned_languages_detects_csharp_and_cplusplus():
    assert tech_stack.mentioned_languages("Wrote a C# service") == {"C#"}
    assert tech_stack.mentioned_languages("Optimized a C++ algorithm") == {"C++"}


def test_mentioned_languages_no_match_returns_empty_set():
    assert tech_stack.mentioned_languages("Did some user research and discovery") == set()


def test_mentioned_languages_java_not_falsely_triggered_by_javascript():
    assert tech_stack.mentioned_languages("Built a frontend in JavaScript") == {"JavaScript"}


def test_mentioned_languages_is_case_insensitive():
    assert tech_stack.mentioned_languages("PYTHON and Sql and pYthOn") == {"Python", "SQL"}
