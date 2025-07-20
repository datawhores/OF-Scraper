from contextlib import contextmanager, asynccontextmanager
import ofscraper.managers.sessionmanager.ofsession as OFsessionManager
import ofscraper.managers.sessionmanager.sessionmanager as sessionManager
class SessionHandler:
    @staticmethod
    @contextmanager
    def get_session( *args, **kwargs):
        with sessionManager.sessionManager(*args, **kwargs) as c:
            yield c
    @staticmethod
    @contextmanager
    def get_ofsession( *args, **kwargs):

        with OFsessionManager.OFSessionManager(*args, **kwargs) as c:
            yield c
    @staticmethod
    @asynccontextmanager
    async def aget_ofsession( *args, **kwargs):

        async with OFsessionManager.OFSessionManager(*args, **kwargs) as c:
            yield c
    @staticmethod
    @contextmanager
    def get_subscription_session(*args, **kwargs):
        with OFsessionManager.SubscriptionSessionManager(*args, **kwargs) as c:
            yield c
    @staticmethod
    @asynccontextmanager
    async def aget_subscription_session( *args, **kwargs):
        async with OFsessionManager.SubscriptionSessionManager(*args, **kwargs) as c:
            yield c
    @staticmethod
    @asynccontextmanager
    async def get_download_session( *args, **kwargs):

        async with OFsessionManager.download_session(*args, **kwargs) as c:
            yield c
    @staticmethod
    @asynccontextmanager
    async def get_metadata_session(*args, **kwargs):
        async with OFsessionManager.metadata_session(*args, **kwargs) as c:
            yield c
    @staticmethod
    @asynccontextmanager
    async def get_cdm_session_manual( *args, **kwargs):

        async with OFsessionManager.cdm_session_manual(*args, **kwargs) as c:
            yield c
    @staticmethod
    @asynccontextmanager
    async def get_cdm_session(*args, **kwargs):

        async with OFsessionManager.cdm_session(*args, **kwargs) as c:
            yield c
    @staticmethod
    @contextmanager
    def get_like_session(*args, **kwargs):
        with OFsessionManager.like_session(*args, **kwargs) as c:
            yield c
sessions = SessionHandler()