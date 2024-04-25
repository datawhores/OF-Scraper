import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.download.shared.globals as common_globals
import ofscraper.utils.constants as constants
from ofscraper.download.shared.classes.retries import get_download_req_retries


class download_session(sessionManager.sessionManager):
    def __init__(
        self,
        sem=None,
        retries=None,
        wait_min=None,
        wait_max=None,
        new_request_auth=None,
    ) -> None:
        sem = sem or common_globals.sem
        retries = retries or get_download_req_retries()
        wait_min = wait_min or constants.getattr("OF_MIN_WAIT_API")
        wait_max = wait_max or constants.getattr("OF_MAX_WAIT_API")
        new_request_auth = new_request_auth if new_request_auth is not None else True
        super().__init__(
            sem=sem,
            retries=retries,
            wait_min=wait_min,
            wait_max=wait_max,
            new_request_auth=new_request_auth,
        )


class cdm_session(sessionManager.sessionManager):
    def __init__(self, backend=None, sem=None, new_request_auth=None) -> None:
        backend = backend or "httpx"
        sem = sem or common_globals.sem
        new_request_auth = new_request_auth if new_request_auth is not None else True
        super().__init__(sem=sem, new_request_auth=new_request_auth, backend=backend)
