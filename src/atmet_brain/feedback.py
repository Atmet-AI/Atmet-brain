"""Opt-in task lifecycle hooks. No implicit transcript capture or publication."""

from copy import deepcopy

from .errors import BrainError, require
from .rpc import dispatch
from .util import text


class TaskClientMixin:
    def task_feedback(self, space_id, report_key, task_key, summary, evidence, audience=None, learn=True):
        return TaskFeedback(self, space_id, report_key, task_key, summary, evidence, audience, learn)


class LocalClient(TaskClientMixin):
    """A token-bound local adapter with the same call interface as remote Client."""

    def __init__(self, brain, token):
        self.brain, self.token = brain, token

    def call(self, method, **params):
        return dispatch(self.brain, self.brain.authenticate(self.token), method, params)

    def review_admin_change(self, **params):
        return self.brain.review_admin_change(self.brain.authenticate(self.token), **params)


class TaskFeedback:
    """Automatically submit a bounded report when an instrumented host task ends.

    The host supplies complete original evidence and safe result text. In-memory
    retry never reruns the business task. A failed draft is exposed in the receipt.
    """

    def __init__(self, client, space_id, report_key, task_key, summary, evidence, audience=None, learn=True):
        self.client = client
        self.params = deepcopy(dict(space_id=space_id, report_key=report_key, task_key=task_key,
                                    summary=summary, evidence=evidence, audience=audience, learn=learn,
                                    steps=[], corrections=[], checks=[]))
        self.receipt, self.error, self._request = None, None, None
        self._entered, self._active = False, False

    def _open(self):
        require(self._request is None, "task_closed", "This completion payload is frozen. Use retry(), or a new report key for a correction.")

    def step(self, value):
        self._append("steps", value, 30)

    def correction(self, value):
        self._append("corrections", value, 20)

    def check(self, value):
        self._append("checks", value, 20)

    def _append(self, key, value, maximum):
        self._open()
        text(value, key, 1000)
        require(len(self.params[key]) < maximum, "invalid_report", "Task feedback exceeds the report limit.")
        self.params[key].append(value)

    def cite(self, evidence):
        """Add original source references actually used by the host task."""
        self._open()
        require(isinstance(evidence, list), "invalid_evidence", "Use a list of original source references.")
        for ref in evidence:
            if ref not in self.params["evidence"]:
                self.params["evidence"].append(deepcopy(ref))

    def result(self, value, outcome="succeeded"):
        self._open()
        text(value, "result", 10000)
        require(outcome in {"succeeded", "failed", "corrected"}, "invalid_report", "Choose succeeded, failed or corrected.")
        self.params.update(result=value, outcome=outcome)

    def submit(self):
        require(not self._active, "task_active", "The host task is still running. Its completion hook submits after it ends.")
        require("result" in self.params, "incomplete_task", "Provide a safe result before completing the task.")
        if self._request is None:
            self._request = deepcopy(self.params)
        self.error = None
        try:
            self.receipt = self.client.call("reports.complete", **deepcopy(self._request))
        except BrainError as error:
            self.error = {"code": error.code, "message": "Task feedback was not acknowledged. Retry the frozen payload; do not rerun the task."}
            raise
        return self.receipt

    def retry(self):
        require(self._request is not None, "incomplete_task", "There is no submitted completion to retry.")
        return self.submit()

    def __enter__(self):
        require(not self._entered and self._request is None, "task_closed", "Use a new feedback session for each task run.")
        self._entered = True
        self._active = True
        return self

    def __exit__(self, error_type, error, traceback):
        self._active = False
        if error_type is not None and not issubclass(error_type, Exception):
            return False  # Do not do network I/O during KeyboardInterrupt/SystemExit.
        if error_type is not None:
            # Raw exception messages, tracebacks, prompts and tool output may contain
            # credentials. The integration can add deliberate safe corrections.
            self.params.update(outcome="failed", result="The host task raised an exception. Error details were withheld.")
        try:
            self.submit()
        except BrainError:
            if error_type is None:
                raise
            # Preserve the original task exception. The host can inspect error and
            # retry the in-memory completion instead of repeating business actions.
        return False

    def run(self, function, *args, **kwargs):
        """Wrap a host callable. It returns safe result text or calls result()."""
        with self:
            value = function(self, *args, **kwargs)
            if "result" not in self.params:
                self.result(value)
        return value
