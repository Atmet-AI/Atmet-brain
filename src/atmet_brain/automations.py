"""Learn repeated pure transformations, review scripts and route matching tasks."""

from pathlib import Path

from .artifacts import effective_version
from .auth import authorize, audience_allows
from .db import audit
from .errors import BrainError, require
from .recipe_runtime import RUNTIME_VERSION, recipe_inputs, records_input, run_recipe, validate_recipe
from .util import dumps, loads, now, sha, slug, text, uid

MIN_RUNS = 3
MAX_TRAINING_RUNS = 10


def python_script(template, parameters):
    """Export readable standalone code; the core never evals stored source text."""
    validate_recipe(template, parameters)
    parameters = loads(dumps(parameters))
    runtime = Path(__file__).with_name("recipe_runtime.py").read_text(encoding="utf-8")
    return (runtime + "\n\nif __name__ == '__main__':\n    import sys\n"
            "    print(json.dumps(run_recipe(" + repr(template) + ", " + repr(parameters)
            + ", json.load(sys.stdin)), ensure_ascii=False))\n")


def validate_automation_body(body):
    keys = {"description", "instructions", "task_key", "workflow_id", "workflow_revision", "template", "parameters",
            "runtime_version", "python_source", "training_run_ids", "context_refs"}
    require(isinstance(body, dict) and set(body) == keys, "invalid_automation", "Provide a complete compiled recipe.")
    text(body["description"], "description", 4000)
    text(body["instructions"], "instructions", 4000)
    slug(body["task_key"])
    text(body["workflow_id"], "workflow_id", 100)
    require(type(body["workflow_revision"]) is int and body["workflow_revision"] > 0,
            "invalid_automation", "Provide a workflow revision.")
    require(type(body["runtime_version"]) is int and body["runtime_version"] == RUNTIME_VERSION,
            "runtime_changed", "The recipe runtime needs revalidation.", 409)
    runs = body["training_run_ids"]
    require(isinstance(runs, list) and MIN_RUNS <= len(runs) <= MAX_TRAINING_RUNS
            and all(isinstance(x, str) for x in runs) and len(set(runs)) == len(runs),
            "invalid_automation", "Provide 3 to 10 distinct training run IDs.")
    require(isinstance(body["context_refs"], list) and bool(body["context_refs"]),
            "invalid_automation", "Provide the approved context snapshot.")
    try:
        expected = python_script(body["template"], body["parameters"])
    except (ValueError, TypeError):
        raise BrainError("invalid_automation", "Unsupported or malformed recipe.") from None
    require(body["python_source"] == expected, "invalid_automation", "Only the exact compiled Python recipe is accepted.")
    return body


def infer_recipe(runs):
    """Try a bounded library against actual outputs; never infer a general program."""
    first_input, first_output = loads(runs[0]["inputs"]), loads(runs[0]["output"])
    try:
        rows = records_input(first_input)
        for run in runs:
            records_input(loads(run["inputs"]))
            if isinstance(first_output, dict) and "records" in first_output:
                records_input(loads(run["output"]))
    except ValueError:
        return None
    if not rows or not isinstance(first_output, dict):
        return None
    candidates = []
    output_rows = first_output.get("records")
    if set(first_output) == {"records"} and isinstance(output_rows, list) and output_rows:
        fields = sorted(output_rows[0]) if isinstance(output_rows[0], dict) else []
        if fields and all(isinstance(row, dict) and set(row) == set(fields) for row in output_rows):
            lower = []
            for field in fields:
                observed = [row.get(field) for run in runs for row in loads(run["output"]).get("records", [])
                            if isinstance(row, dict)]
                original = [row.get(field) for run in runs for row in loads(run["inputs"]).get("records", [])
                            if isinstance(row, dict)]
                if observed and all(isinstance(v, str) and v == v.lower() for v in observed) \
                        and any(isinstance(v, str) and v.strip() != v.strip().lower() for v in original):
                    lower.append(field)
            for sort_by in [None, *fields]:
                for deduplicate in [False, True]:
                    candidates.append(("records.normalize", {"fields": fields, "lowercase_fields": lower,
                                                            "sort_by": sort_by, "deduplicate": deduplicate}))
    if set(first_output) == {"totals", "count"}:
        fields = sorted(rows[0])
        candidates.extend(("records.aggregate", {"group_by": group, "value_field": value})
                          for group in fields for value in fields if group != value)
    for template, parameters in candidates:
        try:
            if all(dumps(run_recipe(template, parameters, loads(run["inputs"]))) == run["output"] for run in runs):
                return template, parameters
        except (ValueError, TypeError, KeyError):
            continue
    return None


class AutomationsMixin:
    def _automation_scope(self, conn, actor, space_id, workflow_id):
        workflow = self._artifact(conn, actor, workflow_id)
        require(workflow["space_id"] == space_id and workflow["kind"] == "workflow",
                "invalid_workflow", "Select an approved workflow in this space.")
        refs, proof, visiting = {}, [], set()

        def load(ident):
            if ident in refs:
                return
            require(ident not in visiting and len(visiting) < 30, "dependency_cycle", "Invalid context dependency graph.", 409)
            visiting.add(ident)
            item = self._artifact(conn, actor, ident)
            version = effective_version(conn, ident)
            require(item["space_id"] == space_id and version is not None,
                    "incomplete_context", "Required approved context is unavailable.", 409)
            for ref in self._evidence(conn, actor, space_id, loads(version["evidence"]), allow_empty=True):
                if ref not in proof:
                    proof.append(ref)
            for ref in self._dependencies(conn, actor, space_id, loads(version["dependencies"])):
                load(ref["artifact_id"])
            refs[ident] = {"artifact_id": ident, "revision": version["revision"]}
            visiting.remove(ident)

        load(workflow_id)
        for item in conn.execute("SELECT * FROM artifacts WHERE space_id=? AND kind IN ('policy','instructions','config')", (space_id,)):
            path = item["instruction_path"]
            if path == "shared" or workflow["instruction_path"] == path or workflow["instruction_path"].startswith(path + "/"):
                if effective_version(conn, item["id"]):
                    load(item["id"])
                else:
                    state = conn.execute("SELECT state FROM artifact_versions WHERE artifact_id=? AND reviewed_at IS NOT NULL "
                                         "AND effective_at<=? ORDER BY revision DESC LIMIT 1", (item["id"], now())).fetchone()
                    require(not state or state[0] != "retracted", "incomplete_context", "Required context was retracted.", 409)
        require(len(refs) <= 30 and len(proof) <= 50, "incomplete_context", "Narrow the automation context.", 409)
        return workflow, sorted(refs.values(), key=lambda x: x["artifact_id"]), proof

    def _read_task_run(self, conn, actor, row):
        self._artifact(conn, actor, row["workflow_id"])
        for ref in loads(row["context_refs"]):
            self._artifact(conn, actor, ref["artifact_id"])
        self._evidence(conn, actor, row["space_id"], loads(row["evidence"]))
        return row

    def record_task_run(self, actor, space_id, run_key, task_key, workflow_id, inputs, output, evidence,
                        succeeded=True, ai_tokens=0):
        text(run_key, "run_key", 200)
        slug(task_key)
        require(type(succeeded) is bool and type(ai_tokens) is int and 0 <= ai_tokens <= 10_000_000,
                "invalid_run", "Provide an outcome and nonnegative reported token count.")
        require(isinstance(inputs, dict) and isinstance(output, dict) and len(dumps(inputs)) + len(dumps(output)) <= 32_000,
                "invalid_run", "Provide bounded JSON input/output objects.")
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "observe")
            authorize(conn, actor, space_id, "contribute")
            workflow, refs, context_proof = self._automation_scope(conn, actor, space_id, workflow_id)
            proof = self._evidence(conn, actor, space_id, evidence)
            proof = self._evidence(conn, actor, space_id, proof + [p for p in context_proof if p not in proof])
            wf_revision = next(ref["revision"] for ref in refs if ref["artifact_id"] == workflow_id)
            old = conn.execute("SELECT * FROM task_runs WHERE space_id=? AND run_key=?", (space_id, run_key)).fetchone()
            values = (task_key, workflow_id, wf_revision, dumps(refs), dumps(inputs), dumps(output), int(succeeded), ai_tokens, dumps(proof))
            if old:
                self._read_task_run(conn, actor, old)
                require(old["recorded_by"] == actor.principal_id and tuple(old[k] for k in
                        ("task_key", "workflow_id", "workflow_revision", "context_refs", "inputs", "output", "succeeded", "ai_tokens", "evidence")) == values,
                        "idempotency_conflict", "Run key already identifies another observation.", 409)
                ident, status = old["id"], "unchanged"
            else:
                ident, status = uid("taskrun"), "recorded"
                conn.execute("INSERT INTO task_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (ident, space_id, run_key, *values, actor.principal_id, now()))
                audit(conn, actor, "task.observe", ident, space_id)
                for item in conn.execute("SELECT * FROM artifacts WHERE space_id=? AND kind='automation'", (space_id,)):
                    for version in conn.execute("SELECT * FROM artifact_versions WHERE artifact_id=? AND state IN ('pending','approved')",
                                                (item["id"],)):
                        body = loads(version["body"])
                        if body["task_key"] != task_key or body["context_refs"] != refs:
                            continue
                        try:
                            predicted = run_recipe(body["template"], body["parameters"], inputs)
                        except ValueError:
                            continue
                        if not succeeded or dumps(predicted) != dumps(output):
                            conn.execute("INSERT OR IGNORE INTO automation_blocks VALUES(?,?,?)", (item["id"], version["revision"], ident))
                            audit(conn, actor, "automation.pause", item["id"], space_id, {"revision": version["revision"]})
        # Recording is durable even when no deterministic candidate can be compiled.
        discovery = self.discover_automation(actor, space_id, task_key, workflow_id)
        return {"id": ident, "status": status, "automation": discovery}

    def discover_automation(self, actor, space_id, task_key, workflow_id, min_runs=MIN_RUNS):
        slug(task_key)
        require(type(min_runs) is int and MIN_RUNS <= min_runs <= MAX_TRAINING_RUNS,
                "invalid_limit", "Use 3 to 10 distinct successful examples.")
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "contribute")
            workflow, refs, proof = self._automation_scope(conn, actor, space_id, workflow_id)
            runs = []
            # A visible failed run in the same context prevents automatic compilation.
            for row in conn.execute("SELECT * FROM task_runs WHERE space_id=? AND task_key=? AND workflow_id=? "
                                    "AND context_refs=? ORDER BY created_at DESC,id DESC LIMIT 100",
                                    (space_id, task_key, workflow_id, dumps(refs))):
                try:
                    self._read_task_run(conn, actor, row)
                except BrainError:
                    continue
                if not row["succeeded"]:
                    return {"status": "ai_required", "reason": "observed_failure_requires_review"}
                runs.append(dict(row))
            unique = {row["inputs"]: row for row in runs}
            if len(unique) < min_runs:
                return {"status": "learning", "distinct_successful_inputs": len(unique), "required": min_runs}
            # Validate all visible runs, including repeated inputs with conflicting outputs.
            recipe = infer_recipe(runs)
            if recipe is None:
                return {"status": "ai_required", "reason": "no_supported_deterministic_recipe"}
            template, parameters = recipe
            training = list(unique.values())[:MAX_TRAINING_RUNS]
            for row in training:
                for ref in loads(row["evidence"]):
                    if ref not in proof:
                        proof.append(ref)
            require(len(proof) <= 50, "incomplete_context", "Narrow the training evidence.", 409)
            name = "repeat_" + sha(dumps([task_key, refs]))[:20]
            existing = conn.execute("SELECT id,head FROM artifacts WHERE space_id=? AND kind='automation' AND slug=?",
                                    (space_id, name)).fetchone()
            if existing:
                self._artifact(conn, actor, existing["id"])
                head = conn.execute("SELECT state,evidence FROM artifact_versions WHERE artifact_id=? AND revision=?",
                                    (existing["id"], existing["head"])).fetchone()
                self._evidence(conn, actor, space_id, loads(head["evidence"]), allow_empty=True)
                return {"status": head["state"], "artifact_id": existing["id"], "revision": existing["head"],
                        "reason": "existing_candidate_requires_its_normal_review_lifecycle"}
            body = {"description": "Repeated task: " + task_key,
                    "instructions": "Run the reviewed pure recipe only within its input contract and pinned context. Otherwise return to the agent.",
                    "task_key": task_key, "workflow_id": workflow_id,
                    "workflow_revision": next(ref["revision"] for ref in refs if ref["artifact_id"] == workflow_id),
                    "template": template, "parameters": parameters, "runtime_version": RUNTIME_VERSION,
                    "python_source": python_script(template, parameters), "context_refs": refs,
                    "training_run_ids": [row["id"] for row in training]}
        try:
            proposal = self.propose_artifact(actor, space_id, "automation", name, body, evidence=proof, dependencies=refs,
                                             instruction_path=workflow["instruction_path"], audience=loads(workflow["audience"]),
                                             reason="Repeated examples match a bounded Python recipe; review required",
                                             idempotency_key="compile_" + sha(dumps([task_key, refs, body])))
        except BrainError as error:
            if error.code != "already_exists":
                raise
            # Another observer may have compiled the same task between transactions.
            return self.discover_automation(actor, space_id, task_key, workflow_id, min_runs)
        return {"status": "pending_review", "artifact_id": proposal["id"], "revision": proposal["revision"],
                "template": template, "training_cases": len(training), "publication_authorized": False}

    def _validate_automation(self, conn, actor, artifact, version):
        body = validate_automation_body(loads(version["body"]))
        workflow, refs, proof = self._automation_scope(conn, actor, artifact["space_id"], body["workflow_id"])
        require(body["context_refs"] == refs and loads(version["dependencies"]) == refs
                and artifact["audience"] == workflow["audience"] and artifact["instruction_path"] == workflow["instruction_path"],
                "automation_context_changed", "Automation context changed; recompile and review.", 409)
        require(body["workflow_revision"] == next(x["revision"] for x in refs if x["artifact_id"] == workflow["id"]),
                "automation_context_changed", "Workflow revision changed.", 409)
        self._evidence(conn, actor, artifact["space_id"], loads(version["evidence"]))
        seen = set()
        for ident in body["training_run_ids"]:
            row = conn.execute("SELECT * FROM task_runs WHERE id=? AND space_id=?", (ident, artifact["space_id"])).fetchone()
            require(row and row["task_key"] == body["task_key"] and row["context_refs"] == dumps(refs) and row["succeeded"],
                    "invalid_training", "Training evidence is unavailable or mismatched.", 409)
            self._read_task_run(conn, actor, row)
            for ref in loads(row["evidence"]):
                if ref not in proof:
                    proof.append(ref)
            try:
                reproduced = dumps(run_recipe(body["template"], body["parameters"], loads(row["inputs"])))
            except (ValueError, TypeError, KeyError):
                raise BrainError("regression_failed", "The recipe cannot process a training input.", 409) from None
            require(reproduced == row["output"],
                    "regression_failed", "The recipe does not reproduce a training output.", 409)
            seen.add(row["inputs"])
        require(len(seen) >= MIN_RUNS and all(ref in loads(version["evidence"]) for ref in proof),
                "invalid_training", "Distinct tests and all source dependencies are required.", 409)
        for row in conn.execute("SELECT * FROM task_runs WHERE space_id=? AND task_key=? AND workflow_id=? AND context_refs=?",
                                (artifact["space_id"], body["task_key"], body["workflow_id"], dumps(refs))):
            try:
                self._read_task_run(conn, actor, row)
                predicted = dumps(run_recipe(body["template"], body["parameters"], loads(row["inputs"])))
            except (BrainError, ValueError, TypeError, KeyError):
                continue
            require(row["succeeded"] and predicted == row["output"], "regression_failed",
                    "A recorded outcome conflicts with this recipe; revalidate the workflow and examples.", 409)
        require(not conn.execute("SELECT 1 FROM automation_blocks WHERE artifact_id=? AND revision=?",
                                 (artifact["id"], version["revision"])).fetchone(),
                "automation_paused", "A conflicting observed result requires revalidation.", 409)
        return body

    def _route_task(self, conn, actor, space_id, task_key, workflow_id, inputs):
        authorize(conn, actor, space_id, "read")
        self._automation_scope(conn, actor, space_id, workflow_id)
        matches = []
        for artifact in conn.execute("SELECT * FROM artifacts WHERE space_id=? AND kind='automation'", (space_id,)):
            version = effective_version(conn, artifact["id"])
            if not version or not audience_allows(conn, actor, artifact["audience"]):
                continue
            body = loads(version["body"])
            if body.get("task_key") != task_key or body.get("workflow_id") != workflow_id:
                continue
            try:
                self._validate_automation(conn, actor, artifact, version)
                recipe_inputs(body["template"], body["parameters"], inputs)
            except (BrainError, ValueError, TypeError, KeyError):
                continue
            matches.append((artifact, version, body))
        return matches

    def route_task(self, actor, space_id, task_key, workflow_id, inputs):
        slug(task_key)
        require(isinstance(inputs, dict) and len(dumps(inputs)) <= 30_000, "invalid_input", "Provide bounded task inputs.")
        with self.store.transaction() as conn:
            matches = self._route_task(conn, actor, space_id, task_key, workflow_id, inputs)
            if len(matches) != 1:
                return {"mode": "agent", "reason": "no_unique_current_approved_recipe", "model_called": False}
            artifact, version, _ = matches[0]
            return {"mode": "script", "artifact_id": artifact["id"], "revision": version["revision"],
                    "template": loads(version["body"])["template"], "runtime": "bounded-python-v1",
                    "model_called": False, "external_actions_authorized": False}

    def run_task(self, actor, space_id, task_key, workflow_id, inputs, idempotency_key):
        slug(task_key)
        text(idempotency_key, "idempotency_key", 200)
        require(isinstance(inputs, dict) and len(dumps(inputs)) <= 30_000, "invalid_input", "Provide bounded task inputs.")
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "process")
            matches = self._route_task(conn, actor, space_id, task_key, workflow_id, inputs)
            if len(matches) != 1:
                return {"mode": "agent", "status": "fallback_required", "reason": "no_unique_current_approved_recipe",
                        "model_called": False, "external_actions_authorized": False}
            artifact, version, body = matches[0]
            output = run_recipe(body["template"], body["parameters"], inputs)
            fingerprint = sha(dumps([task_key, workflow_id, inputs, artifact["id"], version["revision"]]))
            old = conn.execute("SELECT * FROM automation_executions WHERE principal_id=? AND space_id=? AND request_key=?",
                               (actor.principal_id, space_id, idempotency_key)).fetchone()
            if old:
                require(old["fingerprint"] == fingerprint, "idempotency_conflict", "Execution key was used for different content.", 409)
                ident = old["id"]
            else:
                ident = uid("execution")
                conn.execute("INSERT INTO automation_executions VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (ident, space_id, actor.principal_id, idempotency_key, fingerprint, artifact["id"],
                              version["revision"], sha(dumps(inputs)), sha(dumps(output)), now()))
                audit(conn, actor, "automation.run", artifact["id"], space_id,
                      {"revision": version["revision"], "execution_id": ident, "model_calls": 0})
            return {"mode": "script", "status": "completed", "execution_id": ident, "artifact_id": artifact["id"],
                    "revision": version["revision"], "output": output, "model_calls": 0, "external_actions_authorized": False}

    def list_task_runs(self, actor, space_id, task_key, include_payload=False, limit=20):
        slug(task_key)
        require(type(include_payload) is bool and type(limit) is int and 1 <= limit <= 100, "invalid_limit", "Invalid run listing options.")
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "read")
            if include_payload:
                authorize(conn, actor, space_id, "history")
            result = []
            for row in conn.execute("SELECT * FROM task_runs WHERE space_id=? AND task_key=? ORDER BY created_at DESC,id DESC", (space_id, task_key)):
                try:
                    self._read_task_run(conn, actor, row)
                except BrainError:
                    continue
                item = {k: row[k] for k in ("id", "task_key", "workflow_id", "workflow_revision", "succeeded", "ai_tokens", "created_at")}
                if include_payload:
                    item.update(inputs=loads(row["inputs"]), output=loads(row["output"]), evidence=loads(row["evidence"]))
                result.append(item)
                if len(result) == limit:
                    break
            return result
