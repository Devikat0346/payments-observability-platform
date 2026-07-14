from fastapi.testclient import TestClient

from app.main import app


def test_websocket_sends_initial_metrics_tick_on_connect():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "metrics_tick"
            assert "channels" in message["data"]
            assert "rails" in message["data"]
            assert "txn_types" in message["data"]


def test_websocket_streams_live_events_after_the_initial_tick():
    # The simulation engine generates transactions continuously (several per
    # second) and ticks metrics every 2s, so a second message should arrive
    # quickly on any open connection — this exercises the actual pub/sub
    # broadcast path (state.publish -> per-connection queue -> websocket.send),
    # not just the one-off initial send.
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            websocket.receive_json()  # initial metrics_tick
            next_message = websocket.receive_json()
            assert next_message["type"] in (
                "transaction",
                "metrics_tick",
                "incident_start",
                "incident_end",
            )


def test_websocket_disconnect_removes_the_subscriber():
    from app.state import state

    before = len(state.subscribers)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            websocket.receive_json()
            assert len(state.subscribers) == before + 1
    assert len(state.subscribers) == before
