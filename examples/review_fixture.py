"""Scripted human-review fixture for disposable demos, never production credentials."""

DEMO_PASSWORD = "Fictional demo review passphrase 2026!"


def release_demo_source(brain, actor, source):
    """Simulate a separate authorized reviewer in a fictional temporary installation.

    Real agents must request a human review; never embed a real password in code.
    """
    if not brain.whoami(actor)["username"]:
        brain.setup_account(actor, "demo-owner", DEMO_PASSWORD)
    proposal = brain.propose_admin_change(actor, "intake.release", {
        "source_id": source["id"], "expected_revision": source["revision"], "audience": ["space"],
        "classification": "Fictional demo document reviewed for this workspace"},
        "Scripted human-review fixture; real use requires private human approval", "demo-release-" + source["id"])
    brain.review_admin_change(actor, proposal["id"], proposal["digest"], True, DEMO_PASSWORD)
