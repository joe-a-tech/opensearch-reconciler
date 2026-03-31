# OpenSearch Reconciler

A small Python-based OpenSearch reconciler that treats a local Git repository as the source of truth for selected OpenSearch objects.

The goal is to replace a more complex Puppet custom-resource approach with something simpler, easier to reason about, and easier to maintain.

## What it does

The reconciler:

* reads YAML definitions from a local `definitions/` directory
* compares desired state from Git with actual state in OpenSearch
* shows what would change with `plan`
* applies those changes with `apply`
* can optionally delete managed objects that no longer exist in definitions
* aims to be idempotent, so a fresh `plan` after `apply` should ideally show `NOOP` unless there is real drift

It uses raw HTTP via `requests` rather than a higher-level client library, to keep API coverage broad and predictable across OpenSearch object types.

---

## Supported object types

Currently supported:

* tenant
* roles
* role_mappings
* users
* index_templates
* component_templates
* ingest_pipelines
* ism_policies

---

## Definitions layout

Definitions are grouped by customer.

```text
definitions/
  customer-a/
    tenant.yaml
    roles/
      ROLE_NAME.yaml
    role_mappings/
      ROLE_NAME.yaml
    users/
      USER_NAME.yaml
    index_templates/
      TEMPLATE_NAME.yaml
    component_templates/
      COMPONENT_TEMPLATE_NAME.yaml
    ingest_pipelines/
      PIPELINE_NAME.yaml
    ism_policies/
      POLICY_NAME.yaml

  customer-b/
    tenant.yaml
    roles/
      ...
```

### Naming rule

Object names must be globally unique per kind across all customers.

For example:

* `customer-a/roles/reader.yaml`
* `customer-b/roles/reader.yaml`

is **not allowed**.

This keeps plan/apply and delete detection unambiguous.

Tenant is a special case: the tenant object name is the customer directory name.

---

## Management marker

The reconciler annotates desired objects internally with `_reconciler` metadata for management tracking.

Example internal marker:

```yaml
_reconciler:
  managed: true
  customer: customer-a
  kind: roles
  name: reader
```

This metadata is used internally for tracking managed objects.

Important notes:

* `_reconciler` is stripped before sending most objects to OpenSearch
* some object types store management metadata differently:

  * `index_templates` and `component_templates` store it in `_meta`
  * `ism_policies` store a management marker in `description`
  * `ingest_pipelines` do **not** get `_meta` injected

---

## How it works

At a high level:

1. Load YAML definitions from `definitions/`
2. Annotate them with internal management metadata
3. Fetch actual objects from OpenSearch
4. Normalise desired and actual objects before comparing them
5. Build a plan of:

   * `create`
   * `update`
   * `delete`
   * `noop`
6. Optionally apply that plan

---

## Commands

The reconciler currently supports:

* `plan`
* `apply`
* `list`

### `plan`

Shows what would change.

### `apply`

Applies planned creates/updates, and optionally deletes.

Deletes are guarded behind `--confirm-deletes`.

### `list`

Like `plan`, but intended to include no-op entries.

---

## CLI usage

### Basic plan

```bash
python -m opensearch_reconciler.cli plan \
  --definitions-dir ./definitions \
  --base-url https://localhost:9200 \
  --client-cert ../opensearch-docker/certs/admin.pem \
  --client-key ../opensearch-docker/certs/admin-key.pem \
  --verify ../opensearch-docker/certs/root-ca.pem
```

### Plan with detailed drift path

```bash
python -m opensearch_reconciler.cli plan \
  --definitions-dir ./definitions \
  --base-url https://localhost:9200 \
  --client-cert ../opensearch-docker/certs/admin.pem \
  --client-key ../opensearch-docker/certs/admin-key.pem \
  --verify ../opensearch-docker/certs/root-ca.pem \
  --show-diff
```

### Apply changes

```bash
python -m opensearch_reconciler.cli apply \
  --definitions-dir ./definitions \
  --base-url https://localhost:9200 \
  --client-cert ../opensearch-docker/certs/admin.pem \
  --client-key ../opensearch-docker/certs/admin-key.pem \
  --verify ../opensearch-docker/certs/root-ca.pem
```

### Apply and allow deletes

```bash
python -m opensearch_reconciler.cli apply \
  --definitions-dir ./definitions \
  --base-url https://localhost:9200 \
  --client-cert ../opensearch-docker/certs/admin.pem \
  --client-key ../opensearch-docker/certs/admin-key.pem \
  --verify ../opensearch-docker/certs/root-ca.pem \
  --confirm-deletes
```

### Reconcile only one customer

```bash
python -m opensearch_reconciler.cli plan \
  --definitions-dir ./definitions \
  --base-url https://localhost:9200 \
  --client-cert ../opensearch-docker/certs/admin.pem \
  --client-key ../opensearch-docker/certs/admin-key.pem \
  --verify ../opensearch-docker/certs/root-ca.pem \
  --customer customer-a
```

---

## CLI options

Common options:

* `--definitions-dir` - path to definitions directory
* `--base-url` - OpenSearch base URL
* `--username` - basic auth username
* `--password` - basic auth password
* `--verify` - `true`, `false`, or CA path
* `--client-cert` - client certificate path
* `--client-key` - client key path
* `--timeout` - HTTP timeout in seconds
* `--customer` - limit reconciliation to one customer
* `--show-noop` - include `NOOP` results
* `--show-diff` - show first detailed mismatch path for updates
* `--verbose` - enable debug logging

Apply-only option:

* `--confirm-deletes` - actually perform deletes for managed objects missing from definitions

---

## Environment variables

The CLI also supports environment variable defaults:

* `OS_RECONCILE_DEFINITIONS_DIR`
* `OS_RECONCILE_BASE_URL`
* `OS_RECONCILE_USERNAME`
* `OS_RECONCILE_PASSWORD`
* `OS_RECONCILE_VERIFY`
* `OS_RECONCILE_CLIENT_CERT`
* `OS_RECONCILE_CLIENT_KEY`
* `OS_RECONCILE_TIMEOUT`

Example:

```bash
export OS_RECONCILE_BASE_URL="https://localhost:9200"
export OS_RECONCILE_CLIENT_CERT="../opensearch-docker/certs/admin.pem"
export OS_RECONCILE_CLIENT_KEY="../opensearch-docker/certs/admin-key.pem"
export OS_RECONCILE_VERIFY="../opensearch-docker/certs/root-ca.pem"

python -m opensearch_reconciler.cli plan --definitions-dir ./definitions
```

---

## Authentication

The reconciler supports:

* basic auth
* mTLS client certificate authentication

Depending on your cluster configuration, you may use either or both.

Examples:

### Basic auth

```bash
python -m opensearch_reconciler.cli plan \
  --definitions-dir ./definitions \
  --base-url https://localhost:9200 \
  --username admin \
  --password secret \
  --verify false
```

### mTLS

```bash
python -m opensearch_reconciler.cli plan \
  --definitions-dir ./definitions \
  --base-url https://localhost:9200 \
  --client-cert ../opensearch-docker/certs/admin.pem \
  --client-key ../opensearch-docker/certs/admin-key.pem \
  --verify ../opensearch-docker/certs/root-ca.pem
```

---

## Output

The reconciler builds a plan containing actions of:

* `CREATE`
* `UPDATE`
* `DELETE`
* `NOOP`

If `rich` is available, output is shown in a formatted table.

Otherwise it falls back to plain text output.

`--show-diff` helps diagnose drift by showing the first real mismatch path after normalisation.

---

## Behaviour and normalisation

Different OpenSearch object types do not round-trip identically, so the reconciler normalises desired and actual objects before comparing them.

Shared compare behaviour includes:

* stripping internal `_reconciler` marker where appropriate
* removing runtime/generated fields
* pruning empty values
* sorting nested structures for stable comparison

### Roles and role mappings

These are mostly pass-through to the Security API.

### Users

User compare ignores write-only or generated fields such as:

* `hash`
* `password`
* `password_hash`
* `security_roles`
* `opendistro_security_roles`

This avoids false drift after apply.

### Tenants

Tenants are loaded from `tenant.yaml` in each customer directory.

Tenants are treated as managed if they are not reserved/static/hidden.

### Index templates

Special handling includes:

* storing management marker in `_meta`
* flattening `settings.index.*` for comparison
* normalising scalar values like ints/bools to strings where OpenSearch returns them that way
* ignoring `data_stream` during compare in the current implementation

### Component templates

Special handling includes:

* storing management marker in `_meta`
* flattening `settings.index.*`
* normalising scalar values for comparison

### Ingest pipelines

Special handling includes:

* per-pipeline GET/PUT/DELETE support
* some clusters may not support list-all pipelines reliably
* when list-all is unavailable, delete detection for ingest pipelines is skipped
* ingest pipelines do not get `_meta` injected

### ISM policies

Special handling includes:

* missing `.opendistro-ism-config` on a fresh cluster is treated as empty state
* updates require optimistic concurrency:

  * `if_seq_no`
  * `if_primary_term`
* default retry blocks may be removed during compare
* `ism_template` may be normalised into a list form
* managed marker is stored in `description`

---

## Managed delete behaviour

Deletes only apply to objects considered managed by the reconciler.

Deletes are never performed unless:

```bash
--confirm-deletes
```

is explicitly provided.

This is a safety guard to reduce accidental destructive changes.

Managed detection varies by object type:

* security objects: internal `_reconciler.managed == true`
* templates: `_meta.managed == true`
* ISM policies: description contains managed marker
* ingest pipelines: delete detection may be skipped if list-all is unavailable

Reserved/static/hidden built-in objects are not deleted.

---

## Example GitOps workflow

A typical workflow is:

1. Authorised user adds or edits YAML in GitLab
2. Merge request is reviewed and approved
3. Change is merged to the tracked branch
4. Repository is pulled onto the OpenSearch host
5. Reconciler runs from cron or systemd timer
6. Changes are planned/applied against the cluster

In this model, GitLab is effectively the main management UI.

---

## Example YAML

### Role

```yaml
cluster_permissions:
  - "cluster:monitor/health"

index_permissions:
  - index_patterns:
      - "logs-*"
    allowed_actions:
      - "read"
```

### Role mapping

```yaml
users:
  - "svc_customer_a"

backend_roles:
  - "customer-a-readers"

hosts: []
```

### User

```yaml
password: "CHANGE_ME"
backend_roles:
  - "customer-a-readers"
attributes: {}
```

### Tenant

```yaml
description: "Customer A tenant"
```

---

## Project layout

```text
opensearch_reconciler/
  __init__.py
  cli.py
  api.py
  models.py
  loader.py
  plan.py
  output.py
  utils.py
  reconcilers/
    __init__.py
    base.py
    security_base.py
    tenant.py
    roles.py
    role_mappings.py
    users.py
    index_templates.py
    component_templates.py
    ingest_pipelines.py
    ism_policies.py
```

---

## Design principles

This codebase is intentionally conservative.

Goals:

* preserve current working behaviour
* minimise redesign
* keep object types isolated
* keep shared logic genuinely shared
* avoid large cross-cutting rewrites that break stable object types
* keep plan/apply behaviour predictable
* prefer explicitness over cleverness

Each reconciler module is intended to have a consistent shape:

* `kind`
* `list_actual()`
* `get_actual()`
* `create()`
* `update()`
* `delete()`
* `normalise_for_compare()`
* `is_managed()`

---

## Limitations

Current limitations include:

* object names must be globally unique per kind across all customers
* no schema validation is performed before sending payloads to OpenSearch
* ingest pipeline delete detection may be unavailable on some clusters
* comparison logic is intentionally pragmatic and may need adjustment for edge cases
* this is not a generic OpenSearch object manager for every API surface

---

## Why no schema validation?

The reconciler currently acts mostly as a pass-through tool with object-specific compare logic.

That means:

* valid fields supported by the target OpenSearch API should work
* invalid or unsupported fields will be rejected by OpenSearch
* the reconciler does not currently maintain per-object schemas

This is a deliberate tradeoff to keep the tool simpler and lower-maintenance.

---

## Recommended next improvements

Suggested next steps:

* add fixture-based tests per reconciler
* add a systemd service/timer instead of cron
* add locking to prevent overlapping runs
* store plan output in logs or artifacts before apply
* add example definitions for every supported object type
* document per-kind quirks and expected YAML shapes
* optionally add a dry-run CI job for merge requests

---

## Development notes

When changing behaviour:

* prefer incremental changes
* avoid broad rewrites across all modules at once
* treat known-good reconcilers as stable
* prove each object type with:

  * create
  * update
  * noop after apply
  * delete where applicable

A good validation cycle is:

1. run `plan`
2. run `apply`
3. run `plan` again
4. confirm the second plan is `NOOP` unless there is real drift

---

## Status

This project is intended to be an evolutionary replacement for a Puppet custom-resource approach, not a full redesign from scratch.

It preserves:

* definitions-driven management
* raw HTTP interaction
* plan/apply workflow
* idempotence goals
* explicit delete safety

while moving to a modular codebase that is safer to maintain and evolve.
