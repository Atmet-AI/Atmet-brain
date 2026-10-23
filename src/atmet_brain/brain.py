"""One core facade used by Python, CLI, REST and MCP."""

from .artifacts import ArtifactsMixin
from .accounts import AccountsMixin
from .administration import AdministrationMixin
from .automations import AutomationsMixin
from .auth import IdentityMixin
from .backups import BackupsMixin
from .config import Settings, default_home
from .connector_service import ConnectorsMixin
from .db import Store
from .discovery import DiscoveryMixin
from .learning import LearningMixin
from .retrieval import RetrievalMixin
from .sources import SourcesMixin
from .task_reports import TaskReportsMixin


class Brain(AdministrationMixin, AccountsMixin, IdentityMixin, SourcesMixin, ArtifactsMixin, AutomationsMixin, TaskReportsMixin, LearningMixin, RetrievalMixin, DiscoveryMixin, BackupsMixin, ConnectorsMixin):
    def __init__(self, home=None, settings=None):
        self.store = Store(home or default_home())
        self.settings = settings or Settings.load(self.store.home)
