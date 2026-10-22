"""Learn a repeated report, review its Python recipe and reuse it without a model."""

import json
from pathlib import Path
import tempfile

from atmet_brain import Brain


def main():
    with tempfile.TemporaryDirectory(prefix="atmet-automation-") as temporary:
        brain = Brain(Path(temporary) / "brain")
        owner = brain.bootstrap("example-company")
        actor = brain.authenticate(owner["token"])
        space = brain.create_space(actor, "operations")["id"]
        source = brain.put_source(actor, space, "report-examples", "Fictional report examples",
                                  "Accepted examples supplied by a trusted task runtime.")
        evidence = [{"source_id": source["id"], "revision": 1}]
        workflow = brain.propose_artifact(actor, space, "workflow", "department-totals", {
            "instructions": "Group the supplied records by department and total decimal amounts.",
            "steps": [{"id": "total", "instruction": "Return totals without taking external actions."}]},
            evidence=evidence, idempotency_key="workflow")
        brain.review_artifact(actor, workflow["id"], 1, True, "Reviewed fictional workflow")
        examples = [
            ({"records": [{"department": "Sales", "amount": "10.10"}, {"department": "Sales", "amount": "0.20"}]},
             {"totals": [{"group": "Sales", "total": "10.30"}], "count": 2}),
            ({"records": [{"department": "Ops", "amount": "2.00"}]},
             {"totals": [{"group": "Ops", "total": "2.00"}], "count": 1}),
            ({"records": [{"department": "Ops", "amount": "3.20"}, {"department": "Sales", "amount": "8.00"}]},
             {"totals": [{"group": "Ops", "total": "3.20"}, {"group": "Sales", "total": "8.00"}], "count": 2})]
        for index, (inputs, output) in enumerate(examples):
            observation = brain.record_task_run(actor, space, "run-" + str(index), "department-totals", workflow["id"],
                                                inputs, output, evidence, ai_tokens=120)
        candidate = observation["automation"]
        # In an application, present code and examples to the authorized reviewer here.
        brain.review_artifact(actor, candidate["artifact_id"], 1, True, "Reviewed generated Python and regression examples")
        request = {"records": [{"department": "Sales", "amount": "0.10"}, {"department": "Sales", "amount": "0.20"}]}
        print(json.dumps({"candidate": candidate,
                          "route": brain.route_task(actor, space, "department-totals", workflow["id"], request),
                          "result": brain.run_task(actor, space, "department-totals", workflow["id"], request, "new-report")}, indent=2))


if __name__ == "__main__":
    main()
