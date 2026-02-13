from app.infra.db.store import DatabaseStore


def test_database_store_persists_across_instances():
    first = DatabaseStore()
    created = first.create_document(filename="persist.pdf", mime="application/pdf", size=128)

    second = DatabaseStore()
    set_row = second.get_set(created["setId"])
    job_row = second.get_job(created["jobId"])
    questions = second.list_questions_for_set(created["setId"])

    assert set_row is not None
    assert job_row is not None
    assert set_row.status == "extracting"
    assert job_row.status == "queued"
    assert len(questions) == 0
