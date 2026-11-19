import json
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
)
from starlette.routing import Route

from app.ai.opsresolve_service import (
    ask_operations_assistant,
    record_user_resolution,
)
from app.incidents.service import (
    list_incidents,
    raise_incident,
    update_incident,
)


async def home(request):
    return HTMLResponse(HTML_PAGE)


async def ask_api(request: Request):
    payload = await request.json()

    question = str(
        payload.get("question", "")
    ).strip()

    if not question:
        return JSONResponse(
            {
                "error": (
                    "Operational question is required."
                )
            },
            status_code=400,
        )

    result = ask_operations_assistant(
        question=question,
        application_area=payload.get(
            "application_area",
            "ALL",
        ),
        current_status=payload.get(
            "current_status",
            "",
        ),
        attempted_action=payload.get(
            "attempted_action",
            "",
        ),
        visible_error=payload.get(
            "visible_error",
            "",
        ),
        operational_reference=payload.get(
            "operational_reference",
            "",
        ),
    )

    public_result = {
        key: value
        for key, value
        in result.items()
        if key != "_internal"
    }

    return JSONResponse(public_result)


async def resolution_feedback_api(
    request: Request,
):
    payload = await request.json()

    return JSONResponse(
        record_user_resolution(payload)
    )


async def incidents_api(request: Request):
    if request.method == "GET":
        return JSONResponse(
            {
                "incidents": list_incidents()
            }
        )

    payload = await request.json()

    try:
        incident = raise_incident(payload)

        return JSONResponse(
            {
                "incident": incident
            }
        )

    except ValueError as error:
        return JSONResponse(
            {
                "error": str(error)
            },
            status_code=400,
        )


async def incident_update_api(
    request: Request,
):
    incident_id = int(
        request.path_params["incident_id"]
    )

    payload = await request.json()

    try:
        incident = update_incident(
            incident_id=incident_id,
            incident_status=payload.get(
                "incident_status",
                "Investigating",
            ),
            identified_root_cause=(
                payload.get(
                    "identified_root_cause",
                    "",
                )
            ),
            resolution_notes=payload.get(
                "resolution_notes",
                "",
            ),
        )

        return JSONResponse(
            {
                "incident": incident
            }
        )

    except ValueError as error:
        return JSONResponse(
            {
                "error": str(error)
            },
            status_code=400,
        )


HTML_PAGE = r'''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>
<title>OpsResolve AI</title>
<style>
:root {
    --nav: #112d4e;
    --nav-light: #27496d;
    --bg: #f4f7fb;
    --panel: #ffffff;
    --text: #132238;
    --muted: #68758a;
    --border: #dce3ec;
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --success: #067647;
    --success-bg: #ecfdf3;
    --warning-bg: #fff8e6;
    --shadow:
        0 8px 24px rgba(17, 45, 78, 0.10);
}
* {
    box-sizing: border-box;
}
body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family:
        "Segoe UI",
        Arial,
        sans-serif;
}
.layout {
    display: grid;
    grid-template-columns: 275px 1fr;
    min-height: 100vh;
}
.sidebar {
    background:
        linear-gradient(
            180deg,
            var(--nav),
            var(--nav-light)
        );
    color: white;
    padding: 28px 20px;
}
.brand {
    font-size: 26px;
    font-weight: 750;
}
.brand-subtitle {
    color: #cad7e7;
    line-height: 1.45;
    font-size: 14px;
    margin: 10px 0 32px;
}
.nav-button {
    width: 100%;
    padding: 14px 16px;
    margin-bottom: 8px;
    color: #e7f0fa;
    background: transparent;
    border: 0;
    border-radius: 10px;
    text-align: left;
    font-size: 16px;
    cursor: pointer;
}
.nav-button:hover,
.nav-button.active {
    background: rgba(255, 255, 255, 0.14);
    color: white;
}
.main {
    padding: 34px 42px 60px;
}
.header {
    margin-bottom: 26px;
}
.header h1 {
    margin: 0;
    font-size: 34px;
}
.header p {
    color: var(--muted);
    margin-top: 7px;
}
.page {
    display: none;
}
.page.active {
    display: block;
}
.card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 15px;
    box-shadow: var(--shadow);
    padding: 24px;
    margin-bottom: 20px;
}
.hero h2 {
    margin: 0 0 7px;
}
.hero p {
    margin: 0;
    color: var(--muted);
}
.grid {
    display: grid;
    grid-template-columns:
        repeat(2, minmax(0, 1fr));
    gap: 16px;
}
.full {
    grid-column: 1 / -1;
}
label {
    display: block;
    font-weight: 650;
    margin-bottom: 7px;
    font-size: 14px;
}
input,
select,
textarea {
    width: 100%;
    padding: 11px 12px;
    border: 1px solid #cfd8e5;
    border-radius: 9px;
    font: inherit;
    color: var(--text);
    background: white;
}
textarea {
    min-height: 110px;
    resize: vertical;
}
.action {
    padding: 12px 20px;
    border: 0;
    border-radius: 9px;
    background: var(--primary);
    color: white;
    font-weight: 700;
    cursor: pointer;
}
.action:hover {
    background: var(--primary-dark);
}
.secondary {
    color: var(--primary);
    background: white;
    border: 1px solid #b9ccff;
}
.response-panel {
    display: none;
}
.root-cause {
    border-left: 4px solid var(--primary);
    background: #f7f9ff;
    padding: 15px 17px;
    border-radius: 7px;
}
.steps li {
    margin-bottom: 10px;
}
.evidence {
    display: inline-block;
    padding: 5px 9px;
    margin: 3px;
    border-radius: 999px;
    background: #edf3ff;
    color: #3046a6;
    font-size: 12px;
}
.incident-card {
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}
.badge {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 999px;
    font-size: 12px;
    background: var(--warning-bg);
}
.message {
    display: none;
    margin-top: 14px;
    padding: 12px;
    color: var(--success);
    background: var(--success-bg);
    border-radius: 8px;
}
.loading {
    display: none;
    color: var(--muted);
    margin-top: 15px;
}
@media (max-width: 850px) {
    .layout {
        grid-template-columns: 1fr;
    }
    .sidebar {
        display: none;
    }
    .main {
        padding: 20px;
    }
    .grid {
        grid-template-columns: 1fr;
    }
}
</style>
</head>
<body>
<div class="layout">
    <aside class="sidebar">
        <div class="brand">
            OpsResolve AI
        </div>

        <div class="brand-subtitle">
            AI-Powered Operations Assistance
            and Incident Resolution
        </div>

        <button
            class="nav-button active"
            onclick="showPage('assistant', this)"
        >
            Operations Assistant
        </button>

        <button
            class="nav-button"
            onclick="showPage('incidents', this)"
        >
            Incident Management
        </button>

        <button
            class="nav-button"
            onclick="showPage('workspace', this)"
        >
            Resolution Workspace
        </button>

        <button
            class="nav-button"
            onclick="showPage('knowledge', this)"
        >
            Knowledge & Evidence
        </button>
    </aside>

    <main class="main">
        <header class="header">
            <h1>OpsResolve AI</h1>
            <p>
                AI-Powered Operations Assistance
                and Incident Resolution
            </p>
        </header>

        <section
            id="assistant"
            class="page active"
        >
            <div class="card hero">
                <h2>
                    Resolve an operational concern
                </h2>
                <p>
                    Describe the concern and receive
                    an evidence-based root cause and
                    resolution steps.
                </p>
            </div>

            <div class="card">
                <div class="grid">
                    <div class="full">
                        <label>
                            Operational question
                        </label>
                        <textarea
                            id="question"
                        >Why can a confirmed invoice batch not be exported?</textarea>
                    </div>

                    <div>
                        <label>Application area</label>
                        <select id="applicationArea">
                            <option value="ALL">
                                All areas
                            </option>
                            <option value="batch_processing">
                                Batch Processing
                            </option>
                            <option value="invoice_lifecycle">
                                Invoice Lifecycle
                            </option>
                            <option value="d2021">
                                D2021 Processing
                            </option>
                            <option value="access_control">
                                Access and Authorization
                            </option>
                            <option value="reports">
                                Reports
                            </option>
                        </select>
                    </div>

                    <div>
                        <label>Current status</label>
                        <input
                            id="currentStatus"
                            value="Confirmed"
                        >
                    </div>

                    <div>
                        <label>Attempted action</label>
                        <input
                            id="attemptedAction"
                            value="Export batch"
                        >
                    </div>

                    <div>
                        <label>
                            Operational reference,
                            optional
                        </label>
                        <input
                            id="operationalReference"
                            placeholder="Batch, invoice or file reference"
                        >
                    </div>

                    <div class="full">
                        <label>
                            Visible error, optional
                        </label>
                        <input
                            id="visibleError"
                            placeholder="Enter the visible error"
                        >
                    </div>
                </div>

                <div style="margin-top:18px">
                    <button
                        class="action"
                        onclick="askAssistant()"
                    >
                        Get Resolution
                    </button>
                </div>

                <div
                    id="loading"
                    class="loading"
                >
                    Reviewing operational evidence...
                </div>
            </div>

            <div
                id="responsePanel"
                class="response-panel"
            >
                <div class="card">
                    <h2>Response</h2>
                    <p id="responseText"></p>

                    <h3>Root Cause</h3>
                    <div
                        id="rootCause"
                        class="root-cause"
                    ></div>

                    <h3>Resolution Steps</h3>
                    <ol
                        id="resolutionSteps"
                        class="steps"
                    ></ol>

                    <h3>Supporting Evidence</h3>
                    <div id="supportingEvidence"></div>

                    <div
                        style="
                            margin-top:20px;
                            display:flex;
                            gap:10px;
                        "
                    >
                        <button
                            class="action"
                            onclick="markResolved()"
                        >
                            Resolved My Issue
                        </button>

                        <button
                            class="action secondary"
                            onclick="prefillIncident()"
                        >
                            Raise Incident
                        </button>
                    </div>

                    <div
                        id="resolvedMessage"
                        class="message"
                    ></div>
                </div>
            </div>
        </section>

        <section
            id="incidents"
            class="page"
        >
            <div class="card hero">
                <h2>Incident Management</h2>
                <p>
                    Raise an incident only when
                    investigation, access, configuration
                    or production-data changes are required.
                </p>
            </div>

            <div class="card">
                <h3>Raise Incident</h3>

                <div class="grid">
                    <div>
                        <label>Incident title</label>
                        <input id="incidentTitle">
                    </div>

                    <div>
                        <label>Priority</label>
                        <select id="incidentPriority">
                            <option>Low</option>
                            <option selected>Medium</option>
                            <option>High</option>
                            <option>Critical</option>
                        </select>
                    </div>

                    <div class="full">
                        <label>Issue description</label>
                        <textarea
                            id="incidentIssue"
                        ></textarea>
                    </div>

                    <div>
                        <label>Application area</label>
                        <input id="incidentArea">
                    </div>

                    <div>
                        <label>Current status</label>
                        <input id="incidentStatus">
                    </div>

                    <div>
                        <label>Attempted action</label>
                        <input id="incidentAction">
                    </div>

                    <div>
                        <label>
                            Operational reference
                        </label>
                        <input id="incidentReference">
                    </div>

                    <div class="full">
                        <label>Visible error</label>
                        <input id="incidentError">
                    </div>

                    <div class="full">
                        <label>
                            AI-identified root cause
                        </label>
                        <textarea
                            id="incidentRootCause"
                        ></textarea>
                    </div>

                    <div class="full">
                        <label>
                            Steps already attempted
                        </label>
                        <textarea
                            id="incidentSteps"
                        ></textarea>
                    </div>

                    <div>
                        <label>Business impact</label>
                        <input id="incidentImpact">
                    </div>

                    <div>
                        <label>
                            Contact/reference information
                        </label>
                        <input id="incidentContact">
                    </div>
                </div>

                <div style="margin-top:18px">
                    <button
                        class="action"
                        onclick="raiseIncident()"
                    >
                        Raise Incident
                    </button>
                </div>

                <div
                    id="incidentMessage"
                    class="message"
                ></div>
            </div>

            <div class="card">
                <h3>My Incident History</h3>

                <button
                    class="action secondary"
                    onclick="loadIncidents()"
                >
                    Refresh History
                </button>

                <div
                    id="incidentHistory"
                    style="margin-top:18px"
                ></div>
            </div>
        </section>

        <section
            id="workspace"
            class="page"
        >
            <div class="card hero">
                <h2>Resolution Workspace</h2>
                <p>
                    Review incident findings,
                    root causes and recorded
                    resolutions.
                </p>
            </div>

            <div class="card">
                <div id="workspaceIncidents"></div>
            </div>
        </section>

        <section
            id="knowledge"
            class="page"
        >
            <div class="card hero">
                <h2>Knowledge & Evidence</h2>
                <p>
                    Browse operational guidance,
                    business rules, runbooks and
                    known incident resolutions.
                </p>
            </div>

            <div class="grid">
                <div class="card">
                    Invoice Lifecycle
                </div>
                <div class="card">
                    Batch Operations
                </div>
                <div class="card">
                    D2021 Processing
                </div>
                <div class="card">
                    Access and Authorization
                </div>
                <div class="card">
                    Operational Runbooks
                </div>
                <div class="card">
                    Reports and Known Incidents
                </div>
            </div>
        </section>
    </main>
</div>

<script>
let latestResolution = null;


function escapeHtml(text) {
    const element = document.createElement(
        "div"
    );

    element.textContent = text || "";

    return element.innerHTML;
}


function value(id) {
    return document.getElementById(id).value;
}


function showPage(pageId, button) {
    document.querySelectorAll(
        ".page"
    ).forEach(
        page => page.classList.remove(
            "active"
        )
    );

    document.querySelectorAll(
        ".nav-button"
    ).forEach(
        item => item.classList.remove(
            "active"
        )
    );

    document.getElementById(
        pageId
    ).classList.add("active");

    button.classList.add("active");

    if (
        pageId === "incidents"
        || pageId === "workspace"
    ) {
        loadIncidents();
    }
}


async function askAssistant() {
    const loading = document.getElementById(
        "loading"
    );

    loading.style.display = "block";

    const payload = {
        question: value("question"),
        application_area: value(
            "applicationArea"
        ),
        current_status: value(
            "currentStatus"
        ),
        attempted_action: value(
            "attemptedAction"
        ),
        visible_error: value(
            "visibleError"
        ),
        operational_reference: value(
            "operationalReference"
        )
    };

    try {
        const response = await fetch(
            "/api/operations/ask",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify(
                    payload
                )
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.error
                || "Unable to generate response."
            );
        }

        latestResolution = {
            ...payload,
            ...result
        };

        document.getElementById(
            "responseText"
        ).textContent = (
            result.response
        );

        document.getElementById(
            "rootCause"
        ).textContent = (
            result.root_cause
        );

        document.getElementById(
            "resolutionSteps"
        ).innerHTML = (
            result.resolution_steps || []
        ).map(
            step => `
                <li>${escapeHtml(step)}</li>
            `
        ).join("");

        document.getElementById(
            "supportingEvidence"
        ).innerHTML = (
            result.supporting_evidence || []
        ).map(
            item => `
                <span class="evidence">
                    ${escapeHtml(item)}
                </span>
            `
        ).join("");

        document.getElementById(
            "responsePanel"
        ).style.display = "block";
    }
    catch (error) {
        alert(error.message);
    }
    finally {
        loading.style.display = "none";
    }
}


async function markResolved() {
    if (!latestResolution) {
        return;
    }

    const response = await fetch(
        "/api/operations/resolved",
        {
            method: "POST",
            headers: {
                "Content-Type":
                    "application/json"
            },
            body: JSON.stringify(
                latestResolution
            )
        }
    );

    const result = await response.json();

    const message = document.getElementById(
        "resolvedMessage"
    );

    message.textContent = result.message;

    message.style.display = "block";
}


function prefillIncident() {
    if (!latestResolution) {
        return;
    }

    document.getElementById(
        "incidentTitle"
    ).value = (
        latestResolution.root_cause
        || "Operational concern"
    );

    document.getElementById(
        "incidentIssue"
    ).value = (
        latestResolution.question
    );

    document.getElementById(
        "incidentArea"
    ).value = (
        latestResolution.application_area
    );

    document.getElementById(
        "incidentStatus"
    ).value = (
        latestResolution.current_status
    );

    document.getElementById(
        "incidentAction"
    ).value = (
        latestResolution.attempted_action
    );

    document.getElementById(
        "incidentError"
    ).value = (
        latestResolution.visible_error
    );

    document.getElementById(
        "incidentReference"
    ).value = (
        latestResolution
        .operational_reference
    );

    document.getElementById(
        "incidentRootCause"
    ).value = (
        latestResolution.root_cause
    );

    document.getElementById(
        "incidentSteps"
    ).value = (
        latestResolution
        .resolution_steps
        .join("\n")
    );

    const incidentButton = (
        document.querySelectorAll(
            ".nav-button"
        )[1]
    );

    showPage(
        "incidents",
        incidentButton
    );
}


async function raiseIncident() {
    const payload = {
        title: value("incidentTitle"),
        issue_description: value(
            "incidentIssue"
        ),
        application_area: value(
            "incidentArea"
        ),
        current_status: value(
            "incidentStatus"
        ),
        attempted_action: value(
            "incidentAction"
        ),
        visible_error: value(
            "incidentError"
        ),
        operational_reference: value(
            "incidentReference"
        ),
        identified_root_cause: value(
            "incidentRootCause"
        ),
        steps_attempted: value(
            "incidentSteps"
        ),
        business_impact: value(
            "incidentImpact"
        ),
        priority: value(
            "incidentPriority"
        ),
        contact_reference: value(
            "incidentContact"
        )
    };

    const response = await fetch(
        "/api/incidents",
        {
            method: "POST",
            headers: {
                "Content-Type":
                    "application/json"
            },
            body: JSON.stringify(payload)
        }
    );

    const result = await response.json();

    if (!response.ok) {
        alert(result.error);
        return;
    }

    const message = document.getElementById(
        "incidentMessage"
    );

    message.textContent = (
        result.incident.incident_reference
        + " was raised successfully."
    );

    message.style.display = "block";

    loadIncidents();
}


async function loadIncidents() {
    const response = await fetch(
        "/api/incidents"
    );

    const result = await response.json();

    const incidents = (
        result.incidents || []
    );

    const html = incidents.length
        ? incidents.map(
            item => `
                <div class="incident-card">
                    <strong>
                        ${escapeHtml(
                            item.incident_reference
                        )}
                        ·
                        ${escapeHtml(item.title)}
                    </strong>

                    <span class="badge">
                        ${escapeHtml(
                            item.incident_status
                        )}
                    </span>

                    <p>
                        <strong>Priority:</strong>
                        ${escapeHtml(item.priority)}
                        ·
                        <strong>Area:</strong>
                        ${escapeHtml(
                            item.application_area
                        )}
                    </p>

                    <p>
                        <strong>Root cause:</strong>
                        ${escapeHtml(
                            item.identified_root_cause
                            || "Pending investigation"
                        )}
                    </p>

                    <p>
                        <strong>Resolution:</strong>
                        ${escapeHtml(
                            item.resolution_notes
                            || "Pending"
                        )}
                    </p>

                    <div class="header-subtitle">
                        Created:
                        ${escapeHtml(item.created_at)}
                        · Updated:
                        ${escapeHtml(item.updated_at)}
                    </div>
                </div>
            `
        ).join("")
        : `
            <p>
                No incidents have been raised.
            </p>
        `;

    document.getElementById(
        "incidentHistory"
    ).innerHTML = html;

    document.getElementById(
        "workspaceIncidents"
    ).innerHTML = html;
}
</script>
</body>
</html>
'''


routes = [
    Route(
        "/",
        home,
        methods=["GET"],
    ),
    Route(
        "/api/operations/ask",
        ask_api,
        methods=["POST"],
    ),
    Route(
        "/api/operations/resolved",
        resolution_feedback_api,
        methods=["POST"],
    ),
    Route(
        "/api/incidents",
        incidents_api,
        methods=["GET", "POST"],
    ),
    Route(
        "/api/incidents/{incident_id:int}",
        incident_update_api,
        methods=["PUT"],
    ),
]


application = Starlette(
    debug=True,
    routes=routes,
)
