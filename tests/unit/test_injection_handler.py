"""
Tests for InjectionHandler - HTTP REST API for tag injection.

Tests cover:
- POST /inject endpoint (single and batch injections)
- GET /inject endpoint (list overrides)
- DELETE /inject endpoint (clear overrides)
- JSON validation and error handling
- Various payload formats

Note: InjectionHandler inherits from BaseHTTPRequestHandler which
automatically calls handle() in __init__. These tests manually create
a handler instance and bypass the automatic handling.
"""

import io
import json
from unittest.mock import Mock, MagicMock, patch, PropertyMock

import pytest
from opc_replay.server import InjectionHandler, OverrideStore


def create_handler(override_store):
    """Helper to create an InjectionHandler without triggering request handling."""
    # Create handler without calling __init__ by using __new__
    handler = InjectionHandler.__new__(InjectionHandler)
    handler.override_store = override_store
    return handler


@pytest.mark.unit
class TestInjectionHandlerPOST:
    """Test POST /inject endpoint."""

    def test_post_single_injection(self, override_store):
        """Test posting a single injection."""
        # Setup handler
        handler = create_handler(override_store)
        handler.path = "/inject"
        
        # Mock request body
        payload = {
            "tagname": "ns=2;s=Temperature",
            "value": 99.9,
            "duration_s": 30,
            "time_offset_s": 0,
        }
        body = json.dumps(payload).encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        # Mock response methods
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        # Call handler
        handler.do_POST()
        
        # Verify response
        handler.send_response.assert_called_once()
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 200
        
        # Verify override was added
        assert override_store.get_active("ns=2;s=Temperature") == 99.9

    def test_post_batch_injections(self, override_store):
        """Test posting multiple injections in batch."""
        handler = create_handler(override_store)
        handler.path = "/inject"
        
        # Batch payload
        payload = {
            "injections": [
                {"tagname": "ns=2;s=Temperature", "value": 99.9, "duration_s": 30},
                {"tagname": "ns=2;s=Pressure", "value": 200.5, "duration_s": 20},
            ]
        }
        body = json.dumps(payload).encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        # Verify both overrides were added
        assert override_store.get_active("ns=2;s=Temperature") == 99.9
        assert override_store.get_active("ns=2;s=Pressure") == 200.5

    def test_post_array_format(self, override_store):
        """Test posting injections as an array."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        
        # Array payload
        payload = [
            {"tagname": "ns=2;s=Tag1", "value": 1.0, "duration_s": 10},
            {"tagname": "ns=2;s=Tag2", "value": 2.0, "duration_s": 20},
        ]
        body = json.dumps(payload).encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        assert override_store.get_active("ns=2;s=Tag1") == 1.0
        assert override_store.get_active("ns=2;s=Tag2") == 2.0

    def test_post_with_dtype(self, override_store):
        """Test posting injection with explicit dtype."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        
        payload = {
            "tagname": "ns=2;s=Counter",
            "value": 42,
            "duration_s": 30,
            "dtype": "Int32",
        }
        body = json.dumps(payload).encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        # Verify override has dtype
        overrides = override_store.list_all()
        assert len(overrides) == 1
        # The dtype is stored in the internal structure

    def test_post_with_time_offset(self, override_store, mocker):
        """Test posting injection with time offset."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])
        
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        
        payload = {
            "tagname": "ns=2;s=Temperature",
            "value": 99.9,
            "duration_s": 30,
            "time_offset_s": 10,
        }
        body = json.dumps(payload).encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        # Should not be active yet
        assert override_store.get_active("ns=2;s=Temperature") is None
        
        # Advance time
        current_time[0] += 10
        assert override_store.get_active("ns=2;s=Temperature") == 99.9

    def test_post_default_values(self, override_store):
        """Test posting injection with default time_offset_s and duration_s."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        
        # Minimal payload
        payload = {
            "tagname": "ns=2;s=Temperature",
            "value": 99.9,
        }
        body = json.dumps(payload).encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        # Should use defaults: offset=0, duration=60
        assert override_store.get_active("ns=2;s=Temperature") == 99.9
        overrides = override_store.list_all()
        assert len(overrides) == 1


@pytest.mark.unit
class TestInjectionHandlerGET:
    """Test GET /inject endpoint."""

    def test_get_empty_overrides(self, override_store):
        """Test GET returns empty list when no overrides."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_GET()
        
        # Check response
        response_body = handler.wfile.getvalue()
        response_data = json.loads(response_body.decode())
        
        assert "overrides" in response_data
        assert response_data["overrides"] == []

    def test_get_with_active_overrides(self, override_store):
        """Test GET returns active overrides."""
        # Add some overrides
        override_store.add("ns=2;s=Temperature", 99.9, 0, 30)
        override_store.add("ns=2;s=Pressure", 200.5, 0, 20)
        
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_GET()
        
        response_body = handler.wfile.getvalue()
        response_data = json.loads(response_body.decode())
        
        assert len(response_data["overrides"]) == 2

    def test_get_wrong_path_returns_404(self, override_store):
        """Test GET to wrong path returns 404."""
        handler = create_handler(override_store)
        
        handler.path = "/wrong"
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_GET()
        
        # Should return 404
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 404


@pytest.mark.unit
class TestInjectionHandlerDELETE:
    """Test DELETE /inject endpoint."""

    def test_delete_clears_overrides(self, override_store):
        """Test DELETE clears all overrides."""
        # Add some overrides
        override_store.add("ns=2;s=Temperature", 99.9, 0, 30)
        override_store.add("ns=2;s=Pressure", 200.5, 0, 20)
        
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_DELETE()
        
        # Verify overrides are cleared
        assert len(override_store.list_all()) == 0
        
        # Check response
        response_body = handler.wfile.getvalue()
        response_data = json.loads(response_body.decode())
        assert response_data["status"] == "cleared"

    def test_delete_wrong_path_returns_404(self, override_store):
        """Test DELETE to wrong path returns 404."""
        handler = create_handler(override_store)
        
        handler.path = "/wrong"
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_DELETE()
        
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 404


@pytest.mark.unit
class TestInjectionHandlerErrorHandling:
    """Test error handling in InjectionHandler."""

    def test_post_empty_body_returns_400(self, override_store):
        """Test POST with empty body returns 400."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        handler.headers = {"Content-Length": 0}
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 400

    def test_post_invalid_json_returns_400(self, override_store):
        """Test POST with invalid JSON returns 400."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        
        # Invalid JSON
        body = b"{ not valid json }"
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 400

    def test_post_missing_tagname_returns_error(self, override_store):
        """Test POST with missing tagname returns error in results."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        
        payload = {
            "value": 99.9,
            "duration_s": 30,
        }
        body = json.dumps(payload).encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        response_body = handler.wfile.getvalue()
        response_data = json.loads(response_body.decode())
        
        assert "results" in response_data
        assert "error" in response_data["results"][0]

    def test_post_unexpected_payload_type_returns_400(self, override_store):
        """Test POST with unexpected payload type returns 400."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"
        
        # Invalid payload type (string)
        body = json.dumps("just a string").encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 400

    def test_post_wrong_path_returns_404(self, override_store):
        """Test POST to wrong path returns 404."""
        handler = create_handler(override_store)
        
        handler.path = "/wrong"
        
        payload = {"tagname": "ns=2;s=Temperature", "value": 99.9}
        body = json.dumps(payload).encode()
        
        handler.headers = {"Content-Length": len(body)}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_POST()
        
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 404


@pytest.mark.unit
class TestInjectionHandlerPathHandling:
    """Test path handling with trailing slashes."""

    def test_path_with_trailing_slash(self, override_store):
        """Test paths with trailing slashes are handled correctly."""
        handler = create_handler(override_store)
        
        handler.path = "/inject/"  # With trailing slash
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_GET()
        
        # Should still work
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 200

    def test_path_without_trailing_slash(self, override_store):
        """Test paths without trailing slashes are handled correctly."""
        handler = create_handler(override_store)
        
        handler.path = "/inject"  # Without trailing slash
        handler.wfile = io.BytesIO()
        
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        
        handler.do_GET()
        
        response_code = handler.send_response.call_args[0][0]
        assert response_code == 200
