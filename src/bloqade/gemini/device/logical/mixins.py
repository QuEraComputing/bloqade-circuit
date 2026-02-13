from dataclasses import field, dataclass

from qlam_core.common import AppContext
from qlam_core.auth.client import AuthClient


@dataclass
class GeminiAuthMixin:
    context_name: str = field(
        init=False, default="gemini-logical"
    )  # FIXME: get the correct name

    @property
    def app_context(self) -> AppContext:
        return AppContext(self.context_name)

    def authenticate(self):
        with AuthClient(self.app_context) as client:
            if client.is_authenticated():
                return

            return client.login()
