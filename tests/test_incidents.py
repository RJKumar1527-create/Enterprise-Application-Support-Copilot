import app.incidents.service as incidents


def use_temporary_database(
    tmp_path,
    monkeypatch,
):
    database_path = (
        tmp_path
        / "opsresolve_test.db"
    )

    monkeypatch.setattr(
        incidents,
        "DATABASE_PATH",
        database_path,
    )

    incidents.initialise_incidents()

    return database_path


def sample_incident():
    return {
        "title": "Synthetic batch export issue",
        "issue_description": (
            "A confirmed synthetic batch "
            "does not export."
        ),
        "application_area": (
            "batch_processing"
        ),
        "current_status": "Confirmed",
        "attempted_action": "Export batch",
        "visible_error": "",
        "operational_reference": (
            "SYNTH-BATCH-001"
        ),
        "identified_root_cause": (
            "Invoices are not authorized."
        ),
        "steps_attempted": (
            "Invoice statuses reviewed."
        ),
        "business_impact": (
            "Synthetic test impact."
        ),
        "priority": "Medium",
        "contact_reference": (
            "SYNTHETIC-USER"
        ),
    }


def test_raise_incident(
    tmp_path,
    monkeypatch,
):
    use_temporary_database(
        tmp_path,
        monkeypatch,
    )

    incident = incidents.raise_incident(
        sample_incident()
    )

    assert incident["incident_status"] == "Open"
    assert incident[
        "incident_reference"
    ].startswith("INC-")


def test_incident_history(
    tmp_path,
    monkeypatch,
):
    use_temporary_database(
        tmp_path,
        monkeypatch,
    )

    incidents.raise_incident(
        sample_incident()
    )

    history = incidents.list_incidents()

    assert len(history) == 1


def test_resolved_incident_requires_notes(
    tmp_path,
    monkeypatch,
):
    use_temporary_database(
        tmp_path,
        monkeypatch,
    )

    incident = incidents.raise_incident(
        sample_incident()
    )

    try:
        incidents.update_incident(
            incident_id=incident[
                "incident_id"
            ],
            incident_status="Resolved",
            identified_root_cause="",
            resolution_notes="",
        )

        assert False

    except ValueError:
        assert True
