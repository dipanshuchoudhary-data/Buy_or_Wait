# Buy or Wait — Production-Grade Financial Decisioning Agent

## Goal

Build a production-grade agentic financial decisioning platform that processes 250 purchase/payment requests from `dataset/requests.csv` and produces `output.csv` with deterministic, evidence-grounded, safe financial recommendations.

---

## Dataset Summary (Verified)

| File | Rows | Key Fields |
|---|---|---|
| `requests.csv` | 250 | `request_id`, `user_id`, `request_date`, `request_type`, `requested_amount`, `desired_completion_date`, `allows_partial_payment`, `request_text` |
| `sample_requests.csv` | 25 | Same + 7 output columns (ground truth for validation) |
| `financial_profiles.csv` | 275 | `user_id`, `home_currency`, `current_available_balance`, `minimum_balance_to_keep`, priorities, preferences |
| `financial_events.csv` | 25,342 | `event_id`, `user_id`, `event_type`, `amount`, `currency`, `status`, `flexibility`, `linked_event_id` |
| `exchange_rates.csv` | 134 | `rate_date`, `from_currency`, `to_currency`, `rate` |
| `request_payment_options.csv` | 790 | `payment_option_id`, `request_id`, `payment_method`, schedules, fees |
| `messages.csv` | 215 | `message_id`, `user_id`, `request_id`, `related_event_id`, `message_text` |
| `images.csv` | 16 | `image_id`, `user_id`, `request_id`, `related_event_id` |
| Media images | 16 PNGs | Pay slips, receipts, invoices, bills |

### Critical Data Facts

- **16 events have blank amounts** — must extract from linked images via VLM
- **16 images** = payslips, invoices, receipts (IDR, INR, USD currencies)
- **5 currencies**: INR, ZAR, IDR, USD, EUR
- **Event types**: expense, debt_payment, subscription, income, refund, investment_purchase, investment_valuation, investment_sale
- **Statuses**: settled, cancelled, pending, scheduled, failed, unrealized
- **Flexibility**: fixed, stoppable, reducible, reducible_or_stoppable
- **58 events with `linked_event_id`** (lifecycle chains)
- **215 messages** (128 with request_id, 39 with related_event_id)
- **Message source types**: employer, service_provider, bank, merchant, financial_service
- **Messages are in Indonesian (IDR users)**, English, and mixed languages

---

## Output Schema (Exact)

```csv
request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
```

### Allowed Values

| Field | Values |
|---|---|
| `affordability_status` | `affordable_now`, `affordable_with_plan`, `affordable_later`, `not_affordable` |
| `recommended_payment_method` | `full_payment`, `partial_payment`, `installments`, `wait`, `not_recommended` |
| `payment_plan` | `YYYY-MM-DD:amount|YYYY-MM-DD:amount` or `none` |
| `spending_changes_needed` | `stop:<event_id>`, `reduce_to:<event_id>:<amount>` separated by `|`, or `none` |

---

## Extracted Business Rules

### Core Invariants

1. `0 <= amount_safe_to_pay <= requested_amount`
2. Balance must **never** fall below `minimum_balance_to_keep` at any point in the 90-day forecast
3. `amount_safe_to_pay` = max the user can pay on `request_date` **before** optional spending changes, while maintaining the 90-day safety check
4. `earliest_date_for_full_payment` = first date when full amount passes safety check **without** spending changes
5. For `affordable_now`: `earliest_date_for_full_payment == request_date`
6. Empty `earliest_date_for_full_payment` when full payment not safe within forecast period

### Payment Method Rules

- **`full_payment`**: user can pay full amount on request_date, user considers `full_payment`
- **`partial_payment`**: request allows it, user considers it, `0 < safe_amount < requested`, second payment ≤ `desired_completion_date`, exactly 2 payments summing to `requested_amount`
- **`installments`**: must match a supplied payment option exactly, user considers installments, option ≤ `max_installment_months`
- **`wait`**: full payment becomes safe later, user accepts `full_payment`
- **`not_recommended`**: no safe eligible plan exists

### Plan Ranking (when multiple safe plans exist)

1. Complete full request by `desired_completion_date`
2. Require no spending changes
3. Minimize total amount paid (lower financing fees)
4. Start payment earlier
5. Use fewer payments
6. Lowest `payment_option_id` as final tie-breaker

### Financial Event Processing

- **Settled**: already happened, affects balance history
- **Pending debits**: reserve them (reduce available balance)
- **Pending credits**: do NOT count until settled
- **Cancelled/Failed**: ignore (do not affect cash flow)
- **Unrealized (investments)**: do NOT treat as available cash
- **Scheduled**: include in forecast
- **Confirmed salary**: count on its settlement date
- **Recurring**: detect from history, forecast into 90-day window

### Evidence Reconciliation

Priority order:
1. Explicit cancellation, settlement, or amendment
2. Newer record from same source
3. Settled event over estimate/forecast
4. Financially safer interpretation when unresolved

### Spending Changes

- Only **recurring** expenses marked as **flexible** (stoppable/reducible/reducible_or_stoppable) AND in a category the user is **willing to reduce/stop** AND **not protected**
- Max 3 changes
- Stop and reduce same event are mutually exclusive

---

## Proposed Architecture

```
src/
├── api/                        # FastAPI endpoints
│   ├── __init__.py
│   ├── app.py                  # FastAPI app factory
│   ├── routes.py               # API routes
│   └── schemas.py              # Request/Response schemas
├── orchestration/              # LangGraph workflow
│   ├── __init__.py
│   ├── graph.py                # Main LangGraph StateGraph
│   ├── state.py                # BuyWaitState TypedDict
│   └── nodes.py                # Graph node functions
├── agents/                     # LLM-powered agents
│   ├── __init__.py
│   ├── message_agent.py        # Message understanding (multilingual)
│   ├── vision_agent.py         # VLM image extraction
│   ├── reconciliation_agent.py # Evidence conflict resolution
│   └── explanation_agent.py    # Decision explanation generation
├── domain/                     # Deterministic business logic
│   ├── __init__.py
│   ├── finance/
│   │   ├── __init__.py
│   │   ├── cashflow.py         # 90-day balance simulation
│   │   ├── currency.py         # Currency conversion
│   │   ├── events.py           # Event normalization & filtering
│   │   └── recurrence.py       # Recurring expense detection
│   ├── payments/
│   │   ├── __init__.py
│   │   ├── planner.py          # Candidate plan generation
│   │   ├── validator.py        # Plan safety validation
│   │   └── ranker.py           # Plan ranking (deterministic)
│   ├── policies/
│   │   ├── __init__.py
│   │   ├── safety.py           # Financial safety gate
│   │   ├── payment_policy.py   # Payment method eligibility
│   │   ├── spending_policy.py  # Spending change policy
│   │   └── user_prefs.py       # User preference enforcement
│   └── decisions/
│       ├── __init__.py
│       ├── builder.py          # Decision object construction
│       └── output.py           # Output CSV formatting
├── data/                       # Data access layer
│   ├── __init__.py
│   ├── loader.py               # CSV loading & caching
│   └── repositories.py         # Domain-specific data queries
├── models/                     # Pydantic models
│   ├── __init__.py
│   ├── domain.py               # Core domain models
│   ├── evidence.py             # Evidence & facts models
│   ├── financial.py            # Financial state models
│   └── output.py               # Output schema models
├── context/                    # Context engineering
│   ├── __init__.py
│   └── views.py                # Per-agent context views
├── prompts/                    # LLM prompt templates
│   ├── __init__.py
│   ├── message_prompts.py
│   ├── vision_prompts.py
│   ├── reconciliation_prompts.py
│   └── explanation_prompts.py
├── evaluation/                 # Evaluation pipeline
│   ├── __init__.py
│   ├── evaluator.py            # Compare against samples
│   ├── metrics.py              # Accuracy metrics
│   └── usage_report.md         # Token usage report
├── infrastructure/             # Cross-cutting concerns
│   ├── __init__.py
│   ├── config.py               # Configuration management
│   ├── logging.py              # Structured logging
│   └── token_tracker.py        # LLM token usage tracking
└── __init__.py
```

Plus at root:
```
code/main.py                    # Entry point (runs all 250 requests → output.csv)
tests/                          # Unit + integration tests
.env                            # API keys
log.txt                         # AGENTS.md session log
```

---

## Proposed Changes

### Phase 1 — Domain Models & Data Layer

#### [NEW] `src/models/domain.py`
All Pydantic models: `UserProfile`, `FinancialEvent`, `ExchangeRate`, `PaymentOption`, `Request`, `Message`, `ImageRef`

#### [NEW] `src/models/financial.py`
`FinancialState`, `CashflowForecast`, `BalanceProjection`, `RecurringPattern`

#### [NEW] `src/models/evidence.py`
`Evidence`, `FinancialFact`, `EvidenceSource`, `ConflictRecord`

#### [NEW] `src/models/output.py`
`DecisionOutput`, `PaymentPlan`, `SpendingChange` — validated against exact output schema

#### [NEW] `src/data/loader.py`
CSV loading with caching, type coercion, date parsing

#### [NEW] `src/data/repositories.py`
`get_user_profile()`, `get_user_events()`, `get_request_messages()`, `get_request_images()`, `get_payment_options()`, `get_exchange_rate()`

---

### Phase 2 — Deterministic Financial Core

#### [NEW] `src/domain/finance/currency.py`
Currency conversion using `exchange_rates.csv` with date matching

#### [NEW] `src/domain/finance/events.py`
Event normalization: filter cancelled/failed, handle linked events, classify recurring vs one-time, handle pending debits/credits, detect duplicates

#### [NEW] `src/domain/finance/recurrence.py`
Detect recurring patterns from historical events (rent, salary, subscriptions, utilities)

#### [NEW] `src/domain/finance/cashflow.py`
**The most critical module.** 90-day balance simulation:
- Start from `current_available_balance`
- Subtract pending debits
- Add confirmed salary on settlement date
- Project recurring expenses
- Project recurring income
- Simulate proposed payment plan
- Check `minimum_balance_to_keep` at every point
- Calculate `amount_safe_to_pay` and `earliest_date_for_full_payment`

---

### Phase 3 — Payment Planning & Policy

#### [NEW] `src/domain/payments/planner.py`
Generate candidate plans:
- Full payment (if amount_safe_to_pay >= requested_amount)
- Partial payment (if allowed, 2-payment split)
- Each installment option from `request_payment_options.csv`
- Wait (full payment on earliest safe date)
- Spending changes + any of the above

#### [NEW] `src/domain/payments/validator.py`
Validate each candidate against 90-day safety check

#### [NEW] `src/domain/payments/ranker.py`
Deterministic ranking per the 6-criterion priority order

#### [NEW] `src/domain/policies/safety.py`
Safety gate — pure deterministic check, no LLM

#### [NEW] `src/domain/policies/payment_policy.py`
Filter plans by user's `payment_methods_user_will_consider` and `max_installment_months`

#### [NEW] `src/domain/policies/spending_policy.py`
Determine eligible spending changes (flexible, non-protected, in user's willing categories)

#### [NEW] `src/domain/policies/user_prefs.py`
User preference enforcement

---

### Phase 4 — LLM Agents

#### [NEW] `src/agents/message_agent.py`
Extract financial facts from messages (multilingual — Indonesian, English). Structured output:
- Amount changes, cancellations, delays, confirmations
- Salary updates, bonus info
- Event amendments

#### [NEW] `src/agents/vision_agent.py`
Extract amounts from 16 images (payslips, receipts, invoices). Structured output:
- Net pay / total amount
- Currency
- Date
- Confidence score

#### [NEW] `src/agents/reconciliation_agent.py`
Resolve conflicts between CSV data, messages, and images. Only invoked when conflicts detected.

#### [NEW] `src/agents/explanation_agent.py`
Generate `decision_explanation` from structured decision + evidence. Cannot modify financial fields.

---

### Phase 5 — LangGraph Orchestration

#### [NEW] `src/orchestration/state.py`
`BuyWaitState` TypedDict with all workflow fields

#### [NEW] `src/orchestration/graph.py`
LangGraph StateGraph with nodes:
1. `validate_request` — Input validation
2. `load_context` — Load user profile, events, messages, images, payment options
3. `extract_image_amounts` — VLM extraction (conditional — only if images exist for this request)
4. `extract_message_facts` — Message understanding (conditional — only if messages exist)
5. `reconcile_evidence` — Conflict resolution (conditional — only if conflicts detected)
6. `build_financial_state` — Deterministic: normalize events, convert currencies, detect recurrence
7. `run_forecast` — Deterministic: 90-day cashflow simulation
8. `generate_plans` — Deterministic: candidate plan generation
9. `validate_plans` — Deterministic: safety gate
10. `rank_plans` — Deterministic: plan ranking
11. `build_decision` — Deterministic: construct final decision object
12. `generate_explanation` — LLM: create explanation text
13. `validate_output` — Deterministic: schema validation

Conditional routing:
- Skip image extraction if no images for request
- Skip message extraction if no messages for request
- Skip reconciliation if no conflicts
- HITL interrupt if critical uncertainty (logged but auto-resolved for batch)

#### [NEW] `src/orchestration/nodes.py`
Individual node implementations

---

### Phase 6 — Context Engineering

#### [NEW] `src/context/views.py`
Per-agent context builders:
- `VisionContext`: image + expected schema only
- `MessageContext`: messages + user events + schema
- `ForecastContext`: normalized events + balance + income + expenses
- `ExplanationContext`: decision + reason codes + key evidence

---

### Phase 7 — FastAPI Backend

#### [NEW] `src/api/app.py`
FastAPI app with CORS, error handling

#### [NEW] `src/api/routes.py`
- `POST /api/v1/affordability/analyze` — Single request analysis
- `GET /api/v1/affordability/{request_id}` — Get result
- `POST /api/v1/affordability/batch` — Process all 250 requests

#### [NEW] `src/api/schemas.py`
API request/response Pydantic models

---

### Phase 8 — Entry Point & Batch Processing

#### [NEW] `code/main.py`
Main entry point that:
1. Loads all CSVs
2. Pre-extracts all 16 image amounts (batched VLM calls)
3. Pre-extracts all message facts (batched LLM calls)
4. Processes each request through the LangGraph workflow
5. Writes `output.csv` with exact required schema
6. Generates `evaluation/usage_report.md`

---

### Phase 9 — Evaluation

#### [NEW] `src/evaluation/evaluator.py`
Compare output against 25 sample requests:
- `amount_safe_to_pay` accuracy (numeric tolerance)
- `affordability_status` exact match
- `recommended_payment_method` exact match
- `payment_plan` structural match
- `earliest_date_for_full_payment` exact match
- `spending_changes_needed` set match

#### [NEW] `src/evaluation/metrics.py`
Accuracy metrics, confusion matrix, per-field scoring

---

### Phase 10 — Testing & Adversarial

#### [NEW] `tests/test_cashflow.py`
Unit tests for 90-day simulation

#### [NEW] `tests/test_currency.py`
Currency conversion tests

#### [NEW] `tests/test_planner.py`
Payment plan generation tests

#### [NEW] `tests/test_safety.py`
Safety gate tests (ensure no unsafe plans pass)

#### [NEW] `tests/test_output.py`
Output schema validation tests

---

## Open Questions

> [!IMPORTANT]
> **Which LLM provider do you want to use?** The system needs:
> 1. A **text LLM** for message understanding, reconciliation, and explanation (e.g., GPT-4o, Gemini 2.0 Flash, Claude)
> 2. A **VLM** for image extraction (e.g., GPT-4o, Gemini 2.0 Flash with vision)
>
> Please confirm which provider(s) and model(s) you want, and whether you have API keys ready.

> [!IMPORTANT]
> **Token budget**: The system will make ~250 explanation calls + ~215 message extraction calls + ~16 image extraction calls + ~50 reconciliation calls ≈ ~530 LLM calls minimum. With batching/caching this is manageable. Do you have a cost ceiling?

> [!NOTE]
> **Batch vs streaming**: For the hackathon, I recommend processing all 250 requests sequentially with pre-computed image/message extractions cached. The FastAPI layer is for demo/future use — the primary output is the batch `output.csv`.

---

## Verification Plan

### Automated Tests
```bash
uv run pytest tests/ -v --cov=src
```

### Sample Evaluation
```bash
uv run python -m src.evaluation.evaluator
```
Compare against 25 sample requests — target ≥22/25 exact matches on `affordability_status` and `recommended_payment_method`.

### Output Validation
- Schema validation: all 250 rows present, all columns in order
- Value validation: all enum values valid, amounts within bounds
- Consistency: `affordable_now` ↔ `earliest == request_date`, etc.

### Manual Verification
- Spot-check 5 requests end-to-end with financial calculations
- Verify image extractions against actual image content
- Verify message extractions against message text
