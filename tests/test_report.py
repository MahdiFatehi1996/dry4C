from dry4c.model import Duplicate, Span
from dry4c.report import format_text, render_edn


def candidate(score: float = 0.875) -> Duplicate:
    return Duplicate(
        score,
        "c",
        Span("a.c", 10, 14),
        Span("b.c", 20, 24),
        30,
        31,
    )


def test_text_report():
    assert (
        format_text([candidate()])
        == "DUPLICATE score=0.88\n  a.c:10-14\n  b.c:20-24\n"
    )
    assert format_text([]) == "No duplicate candidates found.\n"


def test_edn_report_keeps_the_upstream_snapshot():
    assert render_edn([candidate()]) == (
        "{:candidates [\n"
        " {:score 0.875\n"
        '  :language "c"\n'
        '  :left {:file "a.c", :start-line 10, :end-line 14}\n'
        '  :right {:file "b.c", :start-line 20, :end-line 24}\n'
        "  :left-nodes 30\n"
        "  :right-nodes 31}\n"
        "]}\n"
    )
    assert render_edn([]) == "{:candidates []}\n"


def test_edn_score_is_trimmed_to_twelve_decimals():
    assert " {:score 1.0\n" in render_edn([candidate(1.0)])
    assert " {:score 0.890909090909\n" in render_edn(
        [candidate(0.8909090909090909)]
    )
