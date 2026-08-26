# UI, API, and Backend Service Interaction Flows

How the Streamlit client, the FastAPI service, and the background processing layer interact for a normal applicant submission and for admin users. Every route, stage, and guard shown here is taken from the implementation; see the source map in [architecture.md](architecture.md).

## Legend

| Notation | Meaning |
| --- | --- |
| Solid arrow | Synchronous call on the HTTP request path |
| Dotted arrow | Asynchronous work or polled read |
| Dashed reply in sequences | Response returned to the caller |
| Cylinder | Persistent store |
| "human" label | Action a person must take; never automated |

## 1. Interaction layers

Both actors use the same client and the same service. Only role and ownership change what the service permits.

```mermaid
flowchart LR
    subgraph Client["Browser and UI"]
        Applicant["Applicant"]
        Admin["Admin"]
        Views["Streamlit views<br/>app/views/"]
        Client_API["BackendClient<br/>app/api_client.py"]
    end

    subgraph Service["FastAPI service - backend/app/"]
        Sec["JWT and role guards<br/>security.py"]
        RApps["applications.py"]
        RRev["reviews.py"]
        RSch["schemes.py"]
        ROther["auth, users, notifications"]
    end

    subgraph Backend["Processing and persistence - src/"]
        Jobs["Background job threads"]
        Pipe["ApplicationPipeline<br/>agents/orchestrator.py"]
        Repo["Repository<br/>db/repository.py"]
    end

    DB[("Relational database")]
    Files[("Raw uploads")]
    Vec[("ChromaDB")]

    Applicant --> Views
    Admin --> Views
    Views --> Client_API
    Client_API -->|REST and JSON with bearer token| Sec
    Sec --> RApps
    Sec --> RRev
    Sec --> RSch
    Sec --> ROther
    RApps --> Repo
    RRev --> Repo
    RSch --> Repo
    ROther --> Repo
    RApps -.starts.-> Jobs
    Jobs --> Pipe
    Jobs --> Repo
    Jobs --> Files
    Pipe --> Vec
    Repo --> DB
```

The UI holds no business rules. `BackendClient` is the only place the UI crosses into the service, and the service is the only place authorization is enforced.

## 2. Normal submission flow - applicant

The submit call returns as soon as the upload bytes are read. All extraction, indexing, and duplicate checking happens on a background thread, so the applicant is never blocked by OCR or model latency.

```mermaid
sequenceDiagram
    autonumber
    actor A as Applicant
    participant UI as Streamlit views
    participant C as BackendClient
    participant API as FastAPI service
    participant J as Background job
    participant P as Pipeline
    participant DB as Database

    A->>UI: Enter credentials
    UI->>C: login
    C->>API: POST /api/v1/auth/login
    API-->>C: Bearer token and user
    Note over C: Token stored in session state

    A->>UI: Open schemes
    UI->>C: list_schemes
    C->>API: GET /api/v1/schemes
    API-->>C: Open schemes with scoring pattern

    A->>UI: Upload files or paste text
    UI->>C: submit_application
    C->>API: POST /api/v1/applications
    API->>DB: Create submission, status queued
    API-)J: Start ingestion job
    API-->>C: 201 with submission reference
    Note over A,C: Applicant is free immediately

    J->>J: Extract text and run OCR
    J->>DB: Persist raw files and manifest
    J->>P: Index bundle and check duplicates
    P->>DB: Write analysis events
    J->>DB: Stage awaiting_admin_review
    J->>DB: Notify all admins

    loop While analysis is pending
        A->>UI: Refresh my submissions
        UI->>C: list_my_applications and get_analysis_status
        C->>API: GET /applications and /applications/{id}/status
        API->>DB: Read own submissions only
        API-->>C: Timeline stage and analysis status
    end

    A->>UI: View final outcome
    UI->>C: list_reviews
    C->>API: GET /applications/{id}/reviews
    API-->>C: Human decision and rationale
```

### Applicant capabilities

| Action | Route | Server-side guard |
| --- | --- | --- |
| Register | `POST /api/v1/auth/register` | Always creates an applicant |
| Log in | `POST /api/v1/auth/login` | Credential check, issues JWT |
| Browse schemes | `GET /api/v1/schemes` | Authenticated |
| Submit | `POST /api/v1/applications` | Authenticated, requires file or text |
| Edit submission | `PUT /api/v1/applications/{id}` | Owner only and not locked |
| List own | `GET /api/v1/applications` | Filtered to the caller |
| Poll status | `GET /api/v1/applications/{id}/status` | Ownership check |
| Preview files | `GET /api/v1/applications/{id}/files` | Ownership check |
| Request re-evaluation | `POST /api/v1/applications/{id}/request-reevaluation` | Submitting applicant only |
| Read decisions | `GET /api/v1/applications/{id}/reviews` | Owner or admin |

An applicant cannot read the AI reasoning log. `GET /applications/{id}/events` is admin-only.

### Editability

An edit is accepted only while the submission is unlocked. The service computes one lock reason and publishes it on every submission response, so the UI displays the rule rather than reimplementing it.

```mermaid
flowchart TD
    Start["Applicant opens edit"] --> Check{"Editable?"}
    Check -->|Manually locked| No["Blocked"]
    Check -->|Scheme closing date passed| No
    Check -->|Decision already recorded| No
    Check -->|Admin already assigned| No
    Check -->|Analysis running| No
    Check -->|None apply| Yes["Allow edit"]
    Yes --> Replace["PUT replaces documents"]
    Replace --> Restart["Timeline restarts at ingesting"]
```

## 3. Admin flow - staged review

Admins drive the pipeline in gated steps. Each gate is a separate call, and the AI never advances past a gate on its own.

```mermaid
sequenceDiagram
    autonumber
    actor D as Admin
    actor D2 as Second admin
    participant UI as Streamlit admin views
    participant C as BackendClient
    participant API as FastAPI service
    participant J as Background job
    participant P as Pipeline
    participant DB as Database

    D->>UI: Open review queue
    UI->>C: list_all_applications
    C->>API: GET /api/v1/applications
    API-->>C: All submissions with timeline stage

    D->>UI: Claim the case
    UI->>C: assign_for_analysis
    C->>API: POST /applications/{id}/assign
    API->>DB: Set assigned admin
    API-)J: Start extraction and validation
    API-->>C: Updated submission

    J->>P: Run extraction
    P->>DB: Persist fields and summary
    J->>P: Run validation against scheme
    P->>DB: Persist validation result
    J->>DB: Stage awaiting_admin_validation

    D->>UI: Inspect reasoning log
    UI->>C: list_analysis_events
    C->>API: GET /applications/{id}/events
    API-->>C: Reasoning, tool calls, outputs

    alt Needs correction
        D->>C: submit_validation_feedback
        C->>API: POST /validation/feedback
        Note over API: Assigned admin only
        API-)J: Re-run validation with guidance
    else Accepted
        D->>C: complete_validation
        C->>API: POST /validation/complete
        API-)J: Start scoring
    end

    J->>P: Run scoring with scheme pattern
    P->>DB: Persist score and explanation
    J->>DB: Stage awaiting_score_approval

    alt Score needs rework
        D->>C: submit_score_feedback
        C->>API: POST /score/feedback
        API->>DB: Clear existing approvals
        API-)J: Re-score with guidance
    else Score accepted
        D->>C: approve_score
        C->>API: POST /score/approve
        D2->>C: approve_score
        C->>API: POST /score/approve
        API->>DB: Stage completed after two admins
    end

    D->>UI: Record final decision - human
    UI->>C: submit_review
    C->>API: POST /applications/{id}/review
    API->>DB: Persist decision and rationale
    API-->>C: Case finalized
```

### Admin gate summary

```mermaid
flowchart TD
    Q["Review queue"] --> Assign["Assign - claims the case"]
    Assign --> AI1["Extraction and validation run"]
    AI1 --> Gate1{"Assigned admin reviews"}
    Gate1 -->|Feedback| AI1
    Gate1 -->|Complete| AI2["Scoring runs"]
    AI2 --> Gate2{"Any admin reviews score"}
    Gate2 -->|Guidance| AI2
    Gate2 -->|Approve| Count{"Two distinct admins?"}
    Count -->|No| Gate2
    Count -->|Yes| Done["Timeline completed"]
    Done --> Final["Human decision recorded"]
    Final --> Closed["Approved or rejected"]

    Fail["Any stage fails"] -.-> Restart["Admin restarts from failed stage"]
    Restart -.-> AI1
```

Two distinct rules apply at the gates. Validation feedback and completion are restricted to the admin who claimed the case. Score approval is open to any admin, but completion requires two different admins, enforced by a uniqueness constraint on the approvals table.

### Admin capabilities

| Area | Routes | Guard |
| --- | --- | --- |
| Queue and detail | `GET /applications`, `GET /applications/{id}` | Admin sees all |
| Reasoning log | `GET /applications/{id}/events`, `/events/stream` | Admin only |
| Claim case | `POST /applications/{id}/assign` | Admin, rejects double assignment |
| Validation loop | `POST /validation/feedback`, `POST /validation/complete` | Assigned admin only |
| Scoring loop | `POST /score/feedback`, `POST /score/approve` | Any admin, two needed to complete |
| Recovery | `POST /applications/{id}/restart`, `POST /applications/{id}/analyze` | Admin, failed or assigned case |
| Edit control | `POST /applications/{id}/lock`, `/unlock` | Admin |
| Final decision | `POST /applications/{id}/review` | Admin, rationale required |
| Schemes | `POST /schemes`, `PUT /schemes/{id}`, `POST /{id}/approve-update`, `PATCH /{id}/active`, `PATCH /{id}/closing-date` | Admin, edits need two approvals |
| Users | `GET /users`, `POST /users/admins`, `PATCH /{id}/active`, `POST /{id}/reset-password` | Admin |
| Notifications | `GET`, `POST`, `DELETE /notifications` | Read for all, write for admin |

## 4. Where the two flows meet

```mermaid
flowchart LR
    subgraph AppSide["Applicant"]
        A1["Submit or edit"]
        A2["Poll own status"]
        A3["Request re-evaluation"]
        A4["Read decision"]
    end

    subgraph Service["FastAPI service"]
        S1["Ownership and role checks"]
        S2["Submission record"]
        S3["Notifications"]
    end

    subgraph AdminSide["Admin"]
        B1["Claim case"]
        B2["Gate validation"]
        B3["Gate scoring"]
        B4["Record decision - human"]
    end

    A1 --> S1 --> S2
    A3 --> S1
    S2 -.notifies.-> S3
    S3 -.surfaces.-> B1
    B1 --> S2
    B2 --> S2
    B3 --> S2
    B4 --> S2
    S2 -.visible to owner.-> A2
    S2 -.final outcome.-> A4
```

The submission record is the shared contract. Applicants and admins never call each other; they observe and mutate the same server-owned record under different permissions, and only the review route can set the final approved or rejected status.
