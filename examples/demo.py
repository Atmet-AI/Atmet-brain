"""Run a complete fictional company example in a temporary private directory."""

import json
from pathlib import Path
import tempfile

from review_fixture import release_demo_source
from atmet_brain import Brain
from atmet_brain.auth import ROLES
from atmet_brain.backups import generate_backup_key
from atmet_brain.skills import install_skill


def main():
    examples = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="atmet-example-") as temporary:
        root = Path(temporary)
        brain = Brain(root / "brain")
        owner_key = brain.bootstrap("example-company", "Example owner")
        owner = brain.authenticate(owner_key["token"])
        space = brain.create_space(owner, "sales")["id"]
        catalogue = brain.put_source(owner, space, "catalogue", "Example catalogue",
                                      (examples / "company/catalogue.md").read_text(), authority="authoritative")
        request = brain.put_source(owner, space, "request", "Customer request", (examples / "company/request.txt").read_text())
        release_demo_source(brain, owner, catalogue)
        release_demo_source(brain, owner, request)
        brain.run_jobs(owner, space)
        policy = brain.propose_artifact(owner, space, "policy", "quotation-rules", json.loads((examples / "policy.json").read_text()),
                                          idempotency_key="demo-policy")
        brain.review_artifact(owner, policy["id"], 1, True, "Example owner reviewed")
        skill = install_skill(brain, owner, space, examples / "skills/prepare-quotation")
        brain.review_artifact(owner, skill["id"], 1, True, "Example skill reviewed")
        workflow = brain.propose_artifact(owner, space, "workflow", "customer-quotation", {
            "description": "Prepare and review a customer quotation",
            "instructions": "Use the quotation skill and the current approval rule. Return a draft for review.",
            "trigger": "A customer requests pricing",
            "steps": [{"id": "prepare", "instruction": "Prepare the evidenced quotation draft.", "skill_id": skill["id"]},
                      {"id": "review", "instruction": "Obtain the applicable approval before any delivery action."}],
            "outputs": ["Quotation draft and required approvals"]},
            dependencies=[{"artifact_id": skill["id"], "revision": 1}, {"artifact_id": policy["id"], "revision": 1}],
            idempotency_key="demo-workflow")
        brain.review_artifact(owner, workflow["id"], 1, True, "Example workflow and dependencies reviewed")
        principal = brain.create_principal(owner, "Quotation worker")
        brain.grant(owner, principal["id"], space, ROLES["worker"])
        service_key = brain.create_credential(owner, principal["id"], operations=["read", "contribute", "process", "observe"], space_ids=[space])
        worker = brain.authenticate(service_key["token"])
        context = brain.get_context(worker, space, "Prepare the customer product quotation", artifact_ids=[workflow["id"]])
        generate_backup_key(root / "backup.key")
        backup = brain.create_backup(root / "brain.atmet", root / "backup.key")
        print(json.dumps({"context": context, "manifest": brain.get_manifest(worker, context["manifest_id"]),
                          "backup": {"encrypted": backup["encrypted"], "schema": backup["manifest"]["schema_version"]}}, indent=2))


if __name__ == "__main__":
    main()
