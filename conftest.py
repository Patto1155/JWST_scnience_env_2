"""Offline test isolation; tests must explicitly mock any external transport."""

import os
import ipaddress
import socket

import pytest
import requests

# Set before collection imports the API/database. Never copy a production DB.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def forbid_external_connections(monkeypatch):
    """Fail accidental HTTP/socket traffic instead of downloading or spending money."""

    def blocked(*args, **kwargs):
        raise AssertionError("Tests are offline: mock external network calls explicitly")

    original_connect = socket.socket.connect

    def loopback_only(sock, address):
        # The dashboard's real local HTTP round-trip is meaningful and stays offline.
        if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
            return original_connect(sock, address)
        return blocked()

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(socket.socket, "connect", loopback_only)
    for module_name in ("runner.executor", "runner.scientific_agent"):
        import importlib

        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, "LLM_API_KEY", "")
        monkeypatch.setattr(module, "OPENROUTER_API_KEY", "")
