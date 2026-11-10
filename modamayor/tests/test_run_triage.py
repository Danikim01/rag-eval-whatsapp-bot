from modamayor.run_triage import evaluate_triage, load_questions


def test_evaluate_triage_marks_matches_and_misses():
    questions = [
        {"id": "a", "question": "hola", "history": [], "action": "answer"},
        {"id": "b", "question": "naranja?", "history": [], "action": "clarify"},
    ]
    results = evaluate_triage(questions, generate=lambda p: "answer")
    assert [r["passed"] for r in results] == [True, False]
    assert results[1]["got"] == "answer" and results[1]["expected"] == "clarify"


def test_evaluate_triage_applies_anti_loop_with_history():
    questions = [
        {"id": "c", "question": "x", "history": [["assistant", "no te entendí bien"]], "action": "handoff"}
    ]
    assert evaluate_triage(questions, generate=lambda p: "clarify")[0]["passed"] is True


def test_dataset_is_well_formed():
    questions = load_questions()
    assert len(questions) >= 10
    assert {q["action"] for q in questions} == {"answer", "clarify", "handoff"}
    assert len({q["id"] for q in questions}) == len(questions)
