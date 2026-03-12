"""
Tests for OverrideStore class - thread-safe tag override management.

Tests cover:
- Basic add/get operations
- Timing logic (before activation, during, after expiry)
- Thread safety with concurrent access
- Multiple overlapping overrides on same tag
- List and clear operations
"""

import threading
import time

import pytest

from opc_replay.server import OverrideStore


@pytest.mark.unit
class TestOverrideStoreBasic:
    """Basic functionality tests for OverrideStore."""

    def test_add_and_get_active(self, override_store):
        """Test adding an override and retrieving it when active."""
        # Add override with no offset, 10s duration
        override_store.add(
            tagname="ns=2;s=Temperature",
            value=99.9,
            time_offset_s=0,
            duration_s=10,
        )

        # Should be immediately active
        value = override_store.get_active("ns=2;s=Temperature")
        assert value == 99.9

    def test_get_active_no_override(self, override_store):
        """Test get_active returns None when no override exists."""
        value = override_store.get_active("ns=2;s=NonExistent")
        assert value is None

    def test_clear_all_overrides(self, override_store):
        """Test clearing all overrides."""
        override_store.add("ns=2;s=Temperature", 99.9, 0, 10)
        override_store.add("ns=2;s=Pressure", 200.5, 0, 10)

        assert override_store.get_active("ns=2;s=Temperature") == 99.9

        override_store.clear()

        assert override_store.get_active("ns=2;s=Temperature") is None
        assert override_store.get_active("ns=2;s=Pressure") is None

    def test_list_all_active(self, override_store):
        """Test listing all overrides."""
        override_store.add("ns=2;s=Temperature", 99.9, 0, 10)
        override_store.add("ns=2;s=Pressure", 200.5, 0, 20)

        all_overrides = override_store.list_all()

        assert len(all_overrides) == 2
        assert any(o["tagname"] == "ns=2;s=Temperature" for o in all_overrides)
        assert any(o["tagname"] == "ns=2;s=Pressure" for o in all_overrides)

        # Check structure of returned data
        temp_override = next(o for o in all_overrides if o["tagname"] == "ns=2;s=Temperature")
        assert temp_override["value"] == 99.9
        assert temp_override["active"] is True
        assert temp_override["pending"] is False
        assert "remaining_s" in temp_override


@pytest.mark.unit
class TestOverrideStoreTiming:
    """Test override activation and expiration timing."""

    def test_override_not_active_before_offset(self, override_store, mocker):
        """Test override is not active before offset time."""
        # Mock time.time()
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add override with 5s offset
        override_store.add("ns=2;s=Temperature", 99.9, 5, 10)

        # Should not be active yet
        value = override_store.get_active("ns=2;s=Temperature")
        assert value is None

        # Advance time to activation point
        current_time[0] += 5
        value = override_store.get_active("ns=2;s=Temperature")
        assert value == 99.9

    def test_override_expires_after_duration(self, override_store, mocker):
        """Test override expires after duration."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add override with 0s offset, 5s duration
        override_store.add("ns=2;s=Temperature", 99.9, 0, 5)

        # Should be active immediately
        assert override_store.get_active("ns=2;s=Temperature") == 99.9

        # Advance time to just before expiry
        current_time[0] += 4.5
        assert override_store.get_active("ns=2;s=Temperature") == 99.9

        # Advance past expiry
        current_time[0] += 1
        assert override_store.get_active("ns=2;s=Temperature") is None

    def test_is_overridden_respects_timing(self, override_store, mocker):
        """Test is_overridden returns False before activation."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add override with 5s offset
        override_store.add("ns=2;s=Temperature", 99.9, 5, 10)

        # Should not be overridden yet
        assert override_store.is_overridden("ns=2;s=Temperature", "ns=2;s=Temperature") is False

        # Advance to activation
        current_time[0] += 5
        assert override_store.is_overridden("ns=2;s=Temperature", "ns=2;s=Temperature") is True

        # Advance past expiry
        current_time[0] += 11
        assert override_store.is_overridden("ns=2;s=Temperature", "ns=2;s=Temperature") is False

    def test_list_all_shows_pending_overrides(self, override_store, mocker):
        """Test list_all distinguishes between pending and active overrides."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add override with 5s offset
        override_store.add("ns=2;s=Temperature", 99.9, 5, 10)

        overrides = override_store.list_all()
        assert len(overrides) == 1
        assert overrides[0]["pending"] is True
        assert overrides[0]["active"] is False

        # Advance to activation
        current_time[0] += 5
        overrides = override_store.list_all()
        assert overrides[0]["pending"] is False
        assert overrides[0]["active"] is True


@pytest.mark.unit
class TestOverrideStoreMultiple:
    """Test handling of multiple overrides on the same tag."""

    def test_multiple_overrides_latest_wins(self, override_store, mocker):
        """Test that the most recently added active override takes precedence."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add first override
        override_store.add("ns=2;s=Temperature", 50.0, 0, 20)
        assert override_store.get_active("ns=2;s=Temperature") == 50.0

        # Add second override (should take precedence)
        override_store.add("ns=2;s=Temperature", 99.9, 0, 10)
        assert override_store.get_active("ns=2;s=Temperature") == 99.9

        # After second expires, first should still be active
        current_time[0] += 11
        assert override_store.get_active("ns=2;s=Temperature") == 50.0

    def test_expired_overrides_cleaned_up(self, override_store, mocker):
        """Test that expired overrides are removed from storage."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add short-lived override
        override_store.add("ns=2;s=Temperature", 99.9, 0, 5)

        # Verify it's in the list
        assert len(override_store.list_all()) == 1

        # Advance past expiry
        current_time[0] += 6

        # Access should trigger cleanup
        override_store.get_active("ns=2;s=Temperature")

        # Should be gone from list
        assert len(override_store.list_all()) == 0

    def test_get_all_active_returns_one_per_tag(self, override_store, mocker):
        """Test get_all_active returns only the active override per tag."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add multiple overrides for same tag
        override_store.add("ns=2;s=Temperature", 50.0, 0, 20)
        override_store.add("ns=2;s=Temperature", 99.9, 0, 10)

        # Add override for different tag
        override_store.add("ns=2;s=Pressure", 200.5, 0, 10)

        all_active = override_store.get_all_active()

        # Should have 2 tags, each with one value
        assert len(all_active) == 2
        assert all_active["ns=2;s=Temperature"]["value"] == 99.9  # Latest wins
        assert all_active["ns=2;s=Pressure"]["value"] == 200.5


@pytest.mark.unit
@pytest.mark.threading
class TestOverrideStoreThreadSafety:
    """Test thread safety of OverrideStore with concurrent access."""

    def test_concurrent_add_operations(self, override_store):
        """Test multiple threads adding overrides concurrently."""
        num_threads = 10
        overrides_per_thread = 100

        def add_overrides(thread_id):
            for i in range(overrides_per_thread):
                tagname = f"ns=2;s=Tag{thread_id}_{i}"
                override_store.add(tagname, float(i), 0, 10)

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=add_overrides, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All overrides should be present
        all_overrides = override_store.list_all()
        assert len(all_overrides) == num_threads * overrides_per_thread

    def test_concurrent_add_and_get(self, override_store):
        """Test concurrent add and get operations."""
        num_threads = 5
        iterations = 100
        errors = []

        def add_and_get(thread_id):
            try:
                for i in range(iterations):
                    tagname = f"ns=2;s=Tag{thread_id}"
                    override_store.add(tagname, float(i), 0, 10)
                    value = override_store.get_active(tagname)
                    # Value should be a float (could be from any iteration)
                    assert isinstance(value, float)
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=add_and_get, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # No errors should occur
        assert len(errors) == 0

    def test_concurrent_is_overridden_checks(self, override_store):
        """Test concurrent is_overridden checks don't cause race conditions."""
        # Add some initial overrides
        for i in range(10):
            override_store.add(f"ns=2;s=Tag{i}", float(i), 0, 10)

        results = []

        def check_overrides():
            local_results = []
            for i in range(10):
                tagname = f"ns=2;s=Tag{i}"
                is_overridden = override_store.is_overridden(tagname, tagname)
                local_results.append(is_overridden)
            results.append(local_results)

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=check_overrides)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should see consistent state (all True or all False)
        assert len(results) == 10
        # Each thread should see 10 tags as overridden
        for result in results:
            assert len(result) == 10
            assert all(result)  # All should be True

    def test_concurrent_clear_and_add(self, override_store):
        """Test clearing while other threads are adding."""
        stop_flag = threading.Event()

        def continuous_add():
            counter = 0
            while not stop_flag.is_set():
                override_store.add(f"ns=2;s=Tag{counter}", 1.0, 0, 10)
                counter += 1
                time.sleep(0.001)

        # Start adder thread
        adder_thread = threading.Thread(target=continuous_add)
        adder_thread.start()

        # Clear multiple times
        for _ in range(5):
            time.sleep(0.01)
            override_store.clear()

        # Stop adder
        stop_flag.set()
        adder_thread.join()

        # Final state should be valid (no crashes)
        override_store.clear()
        assert len(override_store.list_all()) == 0


@pytest.mark.unit
class TestOverrideStoreEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_duration_override(self, override_store, mocker):
        """Test override with zero duration expires immediately."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        override_store.add("ns=2;s=Temperature", 99.9, 0, 0)

        # Should be immediately expired
        value = override_store.get_active("ns=2;s=Temperature")
        assert value is None

    def test_negative_offset(self, override_store, mocker):
        """Test override with negative offset activates immediately."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add with negative offset (past activation time)
        override_store.add("ns=2;s=Temperature", 99.9, -10, 20)

        # Should be active immediately
        value = override_store.get_active("ns=2;s=Temperature")
        assert value == 99.9

    def test_is_overridden_with_remapped_nodeid(self, override_store):
        """Test is_overridden checks both original and remapped NodeIds."""
        override_store.add("ns=2;s=Temperature", 99.9, 0, 10)

        # Should find with original
        assert override_store.is_overridden("ns=2;s=Temperature", "ns=2;s=Temperature") is True

        # Should find with either variant
        assert override_store.is_overridden("ns=1;s=Temperature", "ns=2;s=Temperature") is True
        assert override_store.is_overridden("ns=2;s=Temperature", "ns=3;s=Temperature") is True

    def test_is_overridden_fast_path_empty_store(self, override_store):
        """Test is_overridden fast-path when store is empty."""
        # Empty store should return False without acquiring lock
        assert override_store.is_overridden("ns=2;s=Any", "ns=2;s=Any") is False
        assert len(override_store._overrides) == 0

    def test_list_all_excludes_expired(self, override_store, mocker):
        """Test list_all excludes already-expired entries."""
        current_time = [1000000.0]
        mocker.patch("time.time", side_effect=lambda: current_time[0])

        # Add override that's already expired
        override_store.add("ns=2;s=Temperature", 99.9, 0, 5)

        # Advance past expiry
        current_time[0] += 6

        # Should not appear in list_all
        overrides = override_store.list_all()
        assert len(overrides) == 0

    def test_override_with_dtype_preserved(self, override_store):
        """Test that dtype parameter is preserved in override entry."""
        entry = override_store.add(
            tagname="ns=2;s=Temperature", value=99, time_offset_s=0, duration_s=10, dtype="Int32"
        )

        assert entry["dtype"] == "Int32"
        assert entry["value"] == 99
