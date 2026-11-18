from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from types import SimpleNamespace

import pytest
import requests

from agent.maps import GoogleMaps


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                               json=lambda: self.payload)


def provider(payload=None, day=None):
    day = day or datetime.now(ZoneInfo('America/New_York')).date()
    session = Session(payload)
    return GoogleMaps(None, 'test-only', {'p': 'ChIJ_verified'}, str(day), session), day


def point(day, hour):
    return {'date': {'year': day.year, 'month': day.month, 'day': day.day}, 'hour': hour}


def test_live_special_hours_and_no_persistence():
    maps, day = provider()
    maps.session.payload = {'businessStatus': 'OPERATIONAL', 'currentOpeningHours': {
        'periods': [{'open': point(day, 10), 'close': point(day, 15)}]}}
    assert maps.opening_hours('p', day.weekday()) == [(600, 900)]
    assert maps.opening_hours('p', day.weekday()) == [(600, 900)]
    assert len(maps.session.calls) == 2
    assert not hasattr(maps, 'cache_path')


def test_overnight_clips_previous_day():
    maps, day = provider()
    maps.session.payload = {'businessStatus': 'OPERATIONAL', 'currentOpeningHours': {
        'periods': [{'open': point(day - timedelta(days=1), 22), 'close': point(day, 2)}]}}
    assert maps.opening_hours('p', day.weekday()) == [(0, 120)]
    assert maps.opening_hours('p', (day.weekday() - 1) % 7) == []


def test_missing_identity_or_hours_unknown():
    maps, day = provider({'businessStatus': 'OPERATIONAL'})
    assert maps.opening_hours('missing', day.weekday()) is None
    assert not maps.session.calls
    assert maps.opening_hours('p', day.weekday()) is None


def test_closed_business_unknown_not_verified_open():
    maps, day = provider({'businessStatus': 'CLOSED_PERMANENTLY'})
    assert maps.opening_hours('p', day.weekday()) is None


def test_date_required_and_window():
    maps, day = provider()
    maps.trip_date = None
    with pytest.raises(ValueError, match='explicit'):
        maps.opening_hours('p', day.weekday())
    maps.trip_date = str(day + timedelta(days=7))
    with pytest.raises(ValueError, match='six days'):
        maps.travel_minutes((42, -71), (42.1, -71))


def test_routes_validate_and_ceil():
    maps, _ = provider({'routes': [{'duration': '61s'}]})
    assert maps.travel_minutes((42, -71), (42.1, -71)) == 2
    with pytest.raises(ValueError, match='mode'):
        maps.travel_minutes((42, -71), (42.1, -71), 'fly')
    maps.session.payload = {'routes': []}
    with pytest.raises(ValueError, match='no valid route'):
        maps.travel_minutes((42, -71), (42.1, -71))


def test_provider_exception_redacted_and_call_budget():
    maps, _ = provider()
    def fail(*args, **kwargs):
        raise requests.RequestException('secret-provider-payload')
    maps.session.request = fail
    with pytest.raises(ValueError, match='unavailable') as exc:
        maps.travel_minutes((42, -71), (42.1, -71))
    assert 'secret' not in str(exc.value)
    maps.calls = 40
    with pytest.raises(ValueError, match='limit'):
        maps.travel_minutes((42, -71), (42.1, -71))


def test_live_submission_is_rejected_when_constraints_fail(monkeypatch):
    import pandas as pd
    from agent.tools import ToolBox
    index = SimpleNamespace(by_id={'p': 0}, places=pd.DataFrame({'name': ['Place']}))
    maps, _ = provider()
    maps.index = index
    box = ToolBox(index, maps)
    monkeypatch.setattr('agent.validator.validate', lambda *args: [{'type': 'closed'}])
    result = box.run('submit_itinerary', {'stops': [
        {'place_id': 'p', 'arrive': '10:00', 'leave': '11:00'}]})
    assert result['error'] == 'live validation failed'
    assert box.submitted is None
    assert box.maps is not maps


def test_fractional_group_rejected():
    from agent.tools import ToolBox
    box = ToolBox(None, None)
    result = box.run('update_trip_preferences', {'preferences': {'group_size': 1.5}})
    assert 'whole number' in result['error']


def test_live_tool_network_contract_after_request_fork(monkeypatch):
    from agent.tools import ToolBox
    maps, day = provider()
    transport = Session({'businessStatus': 'OPERATIONAL', 'currentOpeningHours': {
        'periods': [{'open': point(day, 10), 'close': point(day, 15)}]}})
    monkeypatch.setattr('agent.maps.requests.Session', lambda: transport)
    box = ToolBox(None, maps, request={'date': str(day)})
    result = box.run('get_opening_hours', {'place_id': 'p', 'day': day.strftime('%A')})
    assert result['hours'] == '10:00-15:00'
    assert len(transport.calls) == 1


def test_agent_ignores_preference_mutation_after_accepted_submission():
    import pandas as pd
    from agent.agent import TripAgent
    index = SimpleNamespace(by_id={'p': 0}, places=pd.DataFrame({'name': ['Place']}))
    calls = [
        SimpleNamespace(type='tool_use', id='1', name='submit_itinerary', input={
            'stops': [{'place_id': 'p', 'arrive': '10:00', 'leave': '11:00'}]}),
        SimpleNamespace(type='tool_use', id='2', name='update_trip_preferences',
                        input={'preferences': {'budget': 0}}),
    ]
    llm = SimpleNamespace(respond=lambda *args: SimpleNamespace(
        content=calls, usage=SimpleNamespace(input_tokens=0, output_tokens=0)))
    result = TripAgent(llm, index, None).run('plan', preferences={'budget': 100})
    assert result['itinerary']
    assert result['preferences']['budget'] == 100
    assert result['tool_calls'] == ['submit_itinerary']
