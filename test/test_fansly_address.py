"""Fansly: a response whose links are signed for another address is asked for
again (#683).

Fansly signs each link for the address the API request came from. On some
VPNs, requests to some of the API host's addresses leave from another address
than the downloads do, and the CDN refuses every link of such a response.

No request is sent anywhere: a fake session answers the API calls from a list
and refuses CDN links signed for the ranges in ``refused``. The addresses are
documentation ranges (RFC 5737).
"""

import asyncio
import base64
import contextlib
import copy
import json

import aiohttp
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.managers.sessionmanager.sessionmanager as sm
from ofscraper.sites.fansly import address, api, constants

OURS, OTHER, THIRD = "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"


def link(signed_for, name="1.png"):
    policy = {
        "Statement": [
            {
                "Resource": f"https://cdn3.fansly.com/100/{name}",
                "Condition": {
                    "DateLessThan": {"AWS:EpochTime": 1900000000},
                    "IpAddress": {"AWS:SourceIp": signed_for},
                },
            }
        ]
    }
    encoded = base64.b64encode(json.dumps(policy).encode()).decode()
    encoded = encoded.replace("+", "-").replace("=", "_").replace("/", "~")
    return f"https://cdn3.fansly.com/100/{name}?Policy={encoded}&Key-Pair-Id=k&Signature=s"


def reply(signed_for, links=2, first=0):
    media = [
        {"id": str(n), "locations": [{"locationId": "1", "location": link(signed_for, f"{n}.png")}]}
        for n in range(first, first + links)
    ]
    return {"success": True, "response": {"posts": [{"id": "5"}], "accountMedia": media}}


class Response:
    def __init__(self, data=None):
        self._data = data

    async def json_(self):
        return copy.deepcopy(self._data)


class Session:
    """API calls are answered from ``replies`` (the last one repeats); a CDN
    link is refused when its range is in ``refused``."""

    def __init__(self, replies, refused=(OTHER, THIRD), cdn_error=None):
        self.replies = replies
        self.refused = set(refused)
        self.cdn_error = cdn_error
        self.api_calls = 0
        self.cdn_calls = []
        self.dns_cleared = 0

    def clear_dns_cache(self):
        self.dns_cleared += 1

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        if "apiv3.fansly.com" in url:
            self.api_calls += 1
            yield Response(self.replies[min(self.api_calls, len(self.replies)) - 1])
            return
        self.cdn_calls.append((address._range(url), kwargs))
        if self.cdn_error:
            raise self.cdn_error
        if address._range(url) in self.refused:
            info = aiohttp.RequestInfo(URL(url), "GET", CIMultiDictProxy(CIMultiDict()), URL(url))
            raise aiohttp.ClientResponseError(info, (), status=403)
        yield Response()


@pytest.fixture(autouse=True)
def fresh():
    address.reset()
    yield
    address.reset()


def get(session, path="post?ids=5"):
    return asyncio.run(api.get_json(session, path))


def ranges(data):
    return set(address.link_ranges(data))


def test_links_for_another_address_are_asked_for_again():
    session = Session([reply(OTHER), reply(OURS)])
    assert ranges(get(session)) == {OURS}
    assert session.api_calls == 2


def test_links_the_cdn_accepts_are_used_as_they_are():
    session = Session([reply(OURS)])
    assert ranges(get(session)) == {OURS}
    assert session.api_calls == 1


def test_each_range_is_tried_on_the_cdn_once():
    session = Session([reply(OTHER), reply(THIRD), reply(OURS)])
    get(session)
    # the second call starts on the refused range again, without a new try
    session.api_calls = 0
    get(session)
    assert [signed_for for signed_for, _ in session.cdn_calls] == [OTHER, THIRD, OURS]
    assert session.api_calls == 3


def test_a_second_files_link_is_tried_from_a_later_response_and_kept():
    session = Session([reply(OURS), reply(OURS), reply(OURS, first=5), reply(OURS, first=9)])
    for _ in range(4):
        get(session)
    # the same files again: no try; other files: one more try, then none
    assert [signed_for for signed_for, _ in session.cdn_calls] == [OURS, OURS]
    kept = address.accepted_links(link(OURS, "other.png"))
    assert len(kept) == 2 and len({k.split("?")[0] for k in kept}) == 2
    assert session.api_calls == 4


def test_a_second_link_the_cdn_refuses_decides_nothing():
    session = Session([reply(OURS), reply(OURS, first=5)])
    get(session)
    session.refused.add(OURS)
    session.api_calls = 1
    assert ranges(get(session)) == {OURS}
    # not asked for again, and the range is still the accepted one
    assert session.api_calls == 2 and session.dns_cleared == 0
    assert address.is_accepted(link(OURS))
    assert len(address.accepted_links(link(OURS, "other.png"))) == 1


def test_the_try_fetches_one_byte_and_sends_no_api_credentials():
    session = Session([reply(OURS)])
    get(session)
    (_, kwargs), = session.cdn_calls
    assert kwargs["headers"] == {"Range": "bytes=0-0"}
    assert kwargs["actions"] == [sm.HEADERS]
    assert kwargs["exceptions"] == [] and kwargs["retries"] == 1


def test_it_gives_up_after_a_few_asks_and_uses_the_links():
    session = Session([reply(OTHER)])
    assert ranges(get(session)) == {OTHER}
    assert session.api_calls == api.ADDRESS_ASKS


def test_after_giving_up_the_refused_range_is_tried_again():
    # this machine's address changed to the range that was refused before
    session = Session([reply(OTHER)])
    get(session)
    session.refused.clear()
    session.api_calls = 0
    assert ranges(get(session)) == {OTHER}
    assert session.api_calls == 1


def test_a_try_that_fails_for_another_reason_decides_nothing():
    session = Session([reply(OTHER)], cdn_error=TimeoutError())
    assert ranges(get(session)) == {OTHER}
    assert session.api_calls == 1
    # and it is tried again on the next response
    get(session)
    assert len(session.cdn_calls) == 2


@pytest.mark.parametrize(
    "location",
    [
        "https://cdn3.fansly.com/100/1.png",
        "https://cdn3.fansly.com/100/1.png?Policy=not-a-policy&Key-Pair-Id=k&Signature=s",
        "https://cdn3.fansly.com/100/1.png?Policy=e30_&Key-Pair-Id=k&Signature=s",
        None,
    ],
)
def test_a_response_without_address_bound_links_is_not_checked(location):
    data = {"success": True, "response": {"accountMedia": [{"locations": [{"location": location}]}]}}
    session = Session([data])
    get(session)
    assert session.api_calls == 1 and session.cdn_calls == []


def test_the_user_is_told_once_and_no_address_is_logged(caplog):
    session = Session([reply(OTHER), reply(OURS), reply(OTHER), reply(OURS)])
    with caplog.at_level("DEBUG", logger="shared"):
        get(session)
        get(session)
    assert caplog.text.count("signed some links for another address") == 1
    for private in ("192.0.2", "198.51.100", "Policy=", "cdn3.fansly.com"):
        assert private not in caplog.text


# ---------------------------------------------------------------- which address

API_ADDRESSES = [
    {"hostname": constants.API_HOST, "host": host, "port": 443}
    for host in ("192.0.2.30", "192.0.2.10", "192.0.2.40", "192.0.2.20")
]


def steered():
    return [a["host"] for a in address.steer(constants.API_HOST, API_ADDRESSES)]


def test_requests_go_to_every_address_until_a_response_is_refused():
    get(Session([reply(OURS)]))
    assert address.steer(constants.API_HOST, API_ADDRESSES) == API_ADDRESSES


def test_a_refused_response_moves_requests_to_the_next_address():
    session = Session([reply(OTHER), reply(THIRD), reply(OURS)])
    get(session)
    # two refusals: the first and the second address were passed over, and
    # the session's remembered addresses were dropped each time
    assert steered() == ["192.0.2.20"]
    assert session.dns_cleared == 2
    # the address stays for the later calls
    get(session)
    assert steered() == ["192.0.2.20"] and session.dns_cleared == 2


def test_steering_goes_round_the_addresses_and_leaves_other_hosts_alone():
    seen = []
    for _ in range(5):
        address.try_next_address(Session([]), constants.api_url("post?ids=5"))
        seen.append(steered()[0])
    assert seen == ["192.0.2.10", "192.0.2.20", "192.0.2.30", "192.0.2.40", "192.0.2.10"]
    cdn = [{"hostname": "cdn3.fansly.com", "host": "192.0.2.50", "port": 443}] * 2
    assert address.steer("cdn3.fansly.com", cdn) == cdn
    assert address.steer(constants.API_HOST, []) == []


def test_the_resolver_steers_the_default_resolvers_answer():
    class Default:
        closed = False

        async def resolve(self, host, port=0, family=0):
            return list(API_ADDRESSES)

        async def close(self):
            self.closed = True

    async def run():
        resolver = address.Resolver()
        await resolver.close()
        resolver._default = default = Default()
        before = await resolver.resolve(constants.API_HOST, 443)
        address.try_next_address(Session([]), constants.api_url("post?ids=5"))
        after = await resolver.resolve(constants.API_HOST, 443)
        await resolver.close()
        return before, after, default.closed

    before, after, closed = asyncio.run(run())
    assert before == API_ADDRESSES
    assert [a["host"] for a in after] == ["192.0.2.10"]
    assert closed is True


def test_an_async_session_resolves_through_the_steering_resolver():
    async def run():
        async with sm.sessionManager() as c:
            connector = c._session.connector
            assert isinstance(connector._resolver, address.Resolver)
            connector._cached_hosts.add(("host.invalid", 443), [])
            c.clear_dns_cache()
            assert ("host.invalid", 443) not in connector._cached_hosts

    asyncio.run(run())
