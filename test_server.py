"""
Tests for Dolpyitcs Analytics Server
Run with: python -m pytest test_server.py -v
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport

# Import server
from server import (
    app,
    load_data,
    save_data,
    add_event,
    get_analytics,
    DATA_FILE,
    utc_now,
)


@pytest.fixture
def temp_data_file():
    """Create a temporary data file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({'events': []}, f)
        temp_path = f.name

    with patch('server.DATA_FILE', temp_path):
        yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def sample_pageview_event():
    """Create a sample pageview event."""
    return {
        'eventType': 'pageview',
        'visitorId': 'vis_abc123',
        'sessionId': 'sess_xyz789',
        'timestamp': utc_now().isoformat().replace('+00:00', 'Z'),
        'url': 'http://example.com/page1',
        'path': '/page1',
        'hostname': 'example.com',
        'referrer': 'https://google.com/search',
        'title': 'Page 1',
        'browser': 'Chrome',
        'os': 'Windows',
        'deviceType': 'Desktop',
        'timezone': 'America/New_York'
    }


@pytest.fixture
def sample_click_event():
    """Create a sample click event."""
    return {
        'eventType': 'click',
        'visitorId': 'vis_abc123',
        'sessionId': 'sess_xyz789',
        'timestamp': utc_now().isoformat().replace('+00:00', 'Z'),
        'elementType': 'button',
        'elementId': 'submit-btn',
        'elementText': 'Submit Form'
    }


@pytest.fixture
def sample_scroll_event():
    """Create a sample scroll depth event."""
    return {
        'eventType': 'scroll_depth',
        'visitorId': 'vis_abc123',
        'sessionId': 'sess_xyz789',
        'timestamp': utc_now().isoformat().replace('+00:00', 'Z'),
        'maxScrollDepth': 75
    }


@pytest.fixture
def sample_time_on_page_event():
    """Create a sample time on page event."""
    return {
        'eventType': 'time_on_page',
        'visitorId': 'vis_abc123',
        'sessionId': 'sess_xyz789',
        'timestamp': utc_now().isoformat().replace('+00:00', 'Z'),
        'timeOnPage': 120
    }


@pytest.fixture
def sample_error_event():
    """Create a sample error event."""
    return {
        'eventType': 'error',
        'visitorId': 'vis_abc123',
        'sessionId': 'sess_xyz789',
        'timestamp': utc_now().isoformat().replace('+00:00', 'Z'),
        'message': 'TypeError: Cannot read property of undefined',
        'source': 'app.js',
        'line': 42
    }


@pytest.fixture
def sample_performance_event():
    """Create a sample performance event."""
    return {
        'eventType': 'performance',
        'visitorId': 'vis_abc123',
        'sessionId': 'sess_xyz789',
        'timestamp': utc_now().isoformat().replace('+00:00', 'Z'),
        'performance': {
            'pageLoadTime': 1500,
            'domContentLoaded': 800,
            'firstByte': 200
        }
    }


class TestDataPersistence:
    """Tests for data loading and saving."""

    @pytest.mark.asyncio
    async def test_load_data_empty_file(self, temp_data_file):
        """Test loading data from empty/new file."""
        with patch('server.DATA_FILE', temp_data_file):
            data = await load_data()
            assert 'events' in data
            assert isinstance(data['events'], list)

    @pytest.mark.asyncio
    async def test_load_data_nonexistent_file(self):
        """Test loading data when file doesn't exist."""
        with patch('server.DATA_FILE', '/nonexistent/path/file.json'):
            data = await load_data()
            assert data == {'events': []}

    @pytest.mark.asyncio
    async def test_save_and_load_data(self, temp_data_file):
        """Test saving and loading data."""
        with patch('server.DATA_FILE', temp_data_file):
            test_data = {'events': [{'test': 'event'}]}
            await save_data(test_data)
            loaded = await load_data()
            assert loaded == test_data

    @pytest.mark.asyncio
    async def test_add_event(self, temp_data_file, sample_pageview_event):
        """Test adding an event."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)
            data = await load_data()
            assert len(data['events']) == 1
            assert data['events'][0]['eventType'] == 'pageview'
            assert 'receivedAt' in data['events'][0]

    @pytest.mark.asyncio
    async def test_add_multiple_events(self, temp_data_file, sample_pageview_event, sample_click_event):
        """Test adding multiple events."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)
            await add_event(sample_click_event)
            data = await load_data()
            assert len(data['events']) == 2

    @pytest.mark.asyncio
    async def test_event_limit(self, temp_data_file):
        """Test that events are limited to 100,000."""
        with patch('server.DATA_FILE', temp_data_file):
            # Create initial data with 100,000 events
            data = {'events': [{'id': i} for i in range(100000)]}
            await save_data(data)

            # Add one more event
            await add_event({'id': 100000})

            loaded = await load_data()
            assert len(loaded['events']) == 100000
            # First event should be removed, last should be the new one
            assert loaded['events'][-1]['id'] == 100000


class TestAnalytics:
    """Tests for analytics calculations."""

    @pytest.mark.asyncio
    async def test_get_analytics_empty(self, temp_data_file):
        """Test analytics with no data."""
        with patch('server.DATA_FILE', temp_data_file):
            analytics = await get_analytics()
            assert analytics['summary']['totalPageviews'] == 0
            assert analytics['summary']['uniqueVisitors'] == 0
            assert analytics['summary']['uniqueSessions'] == 0

    @pytest.mark.asyncio
    async def test_get_analytics_pageviews(self, temp_data_file, sample_pageview_event):
        """Test pageview counting."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)
            await add_event(sample_pageview_event.copy())

            analytics = await get_analytics()
            assert analytics['summary']['totalPageviews'] == 2

    @pytest.mark.asyncio
    async def test_get_analytics_unique_visitors(self, temp_data_file, sample_pageview_event):
        """Test unique visitor counting."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)

            # Add event with different visitor
            event2 = sample_pageview_event.copy()
            event2['visitorId'] = 'vis_different'
            await add_event(event2)

            analytics = await get_analytics()
            assert analytics['summary']['uniqueVisitors'] == 2

    @pytest.mark.asyncio
    async def test_get_analytics_unique_sessions(self, temp_data_file, sample_pageview_event):
        """Test unique session counting."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)

            # Add event with different session
            event2 = sample_pageview_event.copy()
            event2['sessionId'] = 'sess_different'
            await add_event(event2)

            analytics = await get_analytics()
            assert analytics['summary']['uniqueSessions'] == 2

    @pytest.mark.asyncio
    async def test_get_analytics_top_pages(self, temp_data_file, sample_pageview_event):
        """Test top pages calculation."""
        with patch('server.DATA_FILE', temp_data_file):
            # Add 3 events for page1
            for _ in range(3):
                await add_event(sample_pageview_event.copy())

            # Add 1 event for page2
            event2 = sample_pageview_event.copy()
            event2['path'] = '/page2'
            await add_event(event2)

            analytics = await get_analytics()
            assert len(analytics['topPages']) == 2
            assert analytics['topPages'][0]['page'] == '/page1'
            assert analytics['topPages'][0]['views'] == 3
            assert analytics['topPages'][1]['page'] == '/page2'
            assert analytics['topPages'][1]['views'] == 1

    @pytest.mark.asyncio
    async def test_get_analytics_browsers(self, temp_data_file, sample_pageview_event):
        """Test browser breakdown."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)

            event2 = sample_pageview_event.copy()
            event2['browser'] = 'Firefox'
            await add_event(event2)

            analytics = await get_analytics()
            browsers = {b['browser']: b['count'] for b in analytics['browsers']}
            assert 'Chrome' in browsers
            assert 'Firefox' in browsers

    @pytest.mark.asyncio
    async def test_get_analytics_devices(self, temp_data_file, sample_pageview_event):
        """Test device type breakdown."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)

            event2 = sample_pageview_event.copy()
            event2['deviceType'] = 'Mobile'
            await add_event(event2)

            analytics = await get_analytics()
            devices = {d['device']: d['count'] for d in analytics['devices']}
            assert 'Desktop' in devices
            assert 'Mobile' in devices

    @pytest.mark.asyncio
    async def test_get_analytics_referrers(self, temp_data_file, sample_pageview_event):
        """Test referrer breakdown."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)

            event2 = sample_pageview_event.copy()
            event2['referrer'] = 'direct'
            await add_event(event2)

            analytics = await get_analytics()
            referrers = {r['referrer']: r['count'] for r in analytics['topReferrers']}
            assert 'google.com' in referrers
            assert 'direct' in referrers

    @pytest.mark.asyncio
    async def test_get_analytics_scroll_depth(self, temp_data_file, sample_scroll_event):
        """Test average scroll depth calculation."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_scroll_event)

            event2 = sample_scroll_event.copy()
            event2['maxScrollDepth'] = 25
            await add_event(event2)

            analytics = await get_analytics()
            # Average of 75 and 25 = 50
            assert analytics['summary']['avgScrollDepth'] == 50

    @pytest.mark.asyncio
    async def test_get_analytics_time_on_page(self, temp_data_file, sample_time_on_page_event):
        """Test average time on page calculation."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_time_on_page_event)

            event2 = sample_time_on_page_event.copy()
            event2['timeOnPage'] = 60
            await add_event(event2)

            analytics = await get_analytics()
            # Average of 120 and 60 = 90
            assert analytics['summary']['avgTimeOnPage'] == 90

    @pytest.mark.asyncio
    async def test_get_analytics_clicks(self, temp_data_file, sample_click_event):
        """Test click tracking."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_click_event)
            await add_event(sample_click_event.copy())

            analytics = await get_analytics()
            assert len(analytics['topClicks']) == 1
            assert analytics['topClicks'][0]['element'] == 'Submit Form'
            assert analytics['topClicks'][0]['clicks'] == 2

    @pytest.mark.asyncio
    async def test_get_analytics_errors(self, temp_data_file, sample_error_event):
        """Test error tracking."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_error_event)

            analytics = await get_analytics()
            assert len(analytics['topErrors']) == 1
            assert 'TypeError' in analytics['topErrors'][0]['message']

    @pytest.mark.asyncio
    async def test_get_analytics_performance(self, temp_data_file, sample_performance_event):
        """Test performance metrics."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_performance_event)

            analytics = await get_analytics()
            assert analytics['avgPerformance'] is not None
            assert analytics['avgPerformance']['pageLoadTime'] == 1500
            assert analytics['avgPerformance']['domContentLoaded'] == 800
            assert analytics['avgPerformance']['firstByte'] == 200

    @pytest.mark.asyncio
    async def test_get_analytics_views_over_time(self, temp_data_file, sample_pageview_event):
        """Test pageviews over time."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)

            analytics = await get_analytics()
            assert len(analytics['viewsOverTime']) >= 1

    @pytest.mark.asyncio
    async def test_get_analytics_recent_events(self, temp_data_file, sample_pageview_event):
        """Test recent events list."""
        with patch('server.DATA_FILE', temp_data_file):
            await add_event(sample_pageview_event)

            analytics = await get_analytics()
            assert len(analytics['recentEvents']) == 1
            assert analytics['recentEvents'][0]['type'] == 'pageview'


class TestTimeRangeFiltering:
    """Tests for time range filtering."""

    @pytest.mark.asyncio
    async def test_filter_24h(self, temp_data_file, sample_pageview_event):
        """Test 24 hour filtering."""
        with patch('server.DATA_FILE', temp_data_file):
            # Add recent event
            await add_event(sample_pageview_event)

            # Add old event (2 days ago)
            old_event = sample_pageview_event.copy()
            old_time = datetime.now(timezone.utc) - timedelta(days=2)
            old_event['timestamp'] = old_time.isoformat().replace('+00:00', 'Z')
            await add_event(old_event)

            analytics = await get_analytics('24h')
            assert analytics['summary']['totalPageviews'] == 1

    @pytest.mark.asyncio
    async def test_filter_7d(self, temp_data_file, sample_pageview_event):
        """Test 7 day filtering."""
        with patch('server.DATA_FILE', temp_data_file):
            # Add recent event
            await add_event(sample_pageview_event)

            # Add old event (10 days ago)
            old_event = sample_pageview_event.copy()
            old_time = datetime.now(timezone.utc) - timedelta(days=10)
            old_event['timestamp'] = old_time.isoformat().replace('+00:00', 'Z')
            await add_event(old_event)

            analytics = await get_analytics('7d')
            assert analytics['summary']['totalPageviews'] == 1

    @pytest.mark.asyncio
    async def test_filter_30d(self, temp_data_file, sample_pageview_event):
        """Test 30 day filtering."""
        with patch('server.DATA_FILE', temp_data_file):
            # Add recent event
            await add_event(sample_pageview_event)

            # Add old event (45 days ago)
            old_event = sample_pageview_event.copy()
            old_time = datetime.now(timezone.utc) - timedelta(days=45)
            old_event['timestamp'] = old_time.isoformat().replace('+00:00', 'Z')
            await add_event(old_event)

            analytics = await get_analytics('30d')
            assert analytics['summary']['totalPageviews'] == 1

    @pytest.mark.asyncio
    async def test_filter_all(self, temp_data_file, sample_pageview_event):
        """Test all time filtering."""
        with patch('server.DATA_FILE', temp_data_file):
            # Add recent event
            await add_event(sample_pageview_event)

            # Add old event (100 days ago)
            old_event = sample_pageview_event.copy()
            old_time = datetime.now(timezone.utc) - timedelta(days=100)
            old_event['timestamp'] = old_time.isoformat().replace('+00:00', 'Z')
            await add_event(old_event)

            analytics = await get_analytics('all')
            assert analytics['summary']['totalPageviews'] == 2


class TestHTTPEndpoints:
    """Tests for HTTP endpoints using FastAPI TestClient."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data
            assert "version" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/metrics")
            assert response.status_code == 200
            data = response.json()
            assert "requests_total" in data
            assert "events_collected" in data
            assert "errors_total" in data

    @pytest.mark.asyncio
    async def test_collect_endpoint(self, temp_data_file, sample_pageview_event):
        """Test event collection endpoint."""
        with patch('server.DATA_FILE', temp_data_file):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/collect", json=sample_pageview_event)
                assert response.status_code == 200
                assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_collect_invalid_json(self):
        """Test event collection with invalid JSON."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/collect",
                content="invalid json",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_analytics_endpoint(self, temp_data_file):
        """Test analytics endpoint."""
        with patch('server.DATA_FILE', temp_data_file):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/analytics")
                assert response.status_code == 200
                data = response.json()
                assert "summary" in data
                assert "topPages" in data

    @pytest.mark.asyncio
    async def test_analytics_endpoint_with_range(self, temp_data_file):
        """Test analytics endpoint with time range parameter."""
        with patch('server.DATA_FILE', temp_data_file):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/analytics?range=24h")
                assert response.status_code == 200


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_malformed_timestamp(self, temp_data_file):
        """Test handling of malformed timestamps."""
        with patch('server.DATA_FILE', temp_data_file):
            event = {
                'eventType': 'pageview',
                'visitorId': 'vis_123',
                'timestamp': 'invalid-timestamp'
            }
            await add_event(event)

            # Should not crash
            analytics = await get_analytics()
            assert analytics['summary']['totalPageviews'] == 0  # Invalid timestamp filtered out

    @pytest.mark.asyncio
    async def test_missing_fields(self, temp_data_file):
        """Test handling of events with missing fields."""
        with patch('server.DATA_FILE', temp_data_file):
            event = {
                'eventType': 'pageview',
                'timestamp': utc_now().isoformat().replace('+00:00', 'Z')
                # Missing visitorId, path, etc.
            }
            await add_event(event)

            # Should not crash
            analytics = await get_analytics()
            assert analytics is not None

    @pytest.mark.asyncio
    async def test_empty_referrer(self, temp_data_file, sample_pageview_event):
        """Test handling of empty referrer."""
        with patch('server.DATA_FILE', temp_data_file):
            sample_pageview_event['referrer'] = ''
            await add_event(sample_pageview_event)

            analytics = await get_analytics()
            assert analytics is not None

    @pytest.mark.asyncio
    async def test_very_long_text(self, temp_data_file, sample_click_event):
        """Test handling of very long text in click events."""
        with patch('server.DATA_FILE', temp_data_file):
            sample_click_event['elementText'] = 'A' * 1000  # Very long text
            await add_event(sample_click_event)

            analytics = await get_analytics()
            # Should be truncated to 50 chars
            assert len(analytics['topClicks'][0]['element']) <= 50


class TestIntegration:
    """Integration tests combining multiple features."""

    @pytest.mark.asyncio
    async def test_full_user_session(self, temp_data_file):
        """Test a complete user session with multiple event types."""
        with patch('server.DATA_FILE', temp_data_file):
            now = utc_now()
            timestamp = now.isoformat().replace('+00:00', 'Z')
            visitor_id = 'vis_integration_test'
            session_id = 'sess_integration_test'

            # User visits page
            await add_event({
                'eventType': 'pageview',
                'visitorId': visitor_id,
                'sessionId': session_id,
                'timestamp': timestamp,
                'path': '/home',
                'browser': 'Chrome',
                'os': 'Windows',
                'deviceType': 'Desktop',
                'referrer': 'https://google.com'
            })

            # User clicks a button
            await add_event({
                'eventType': 'click',
                'visitorId': visitor_id,
                'sessionId': session_id,
                'timestamp': timestamp,
                'elementText': 'Buy Now'
            })

            # User scrolls
            await add_event({
                'eventType': 'scroll_depth',
                'visitorId': visitor_id,
                'sessionId': session_id,
                'timestamp': timestamp,
                'maxScrollDepth': 80
            })

            # User leaves page
            await add_event({
                'eventType': 'time_on_page',
                'visitorId': visitor_id,
                'sessionId': session_id,
                'timestamp': timestamp,
                'timeOnPage': 45
            })

            # Performance data
            await add_event({
                'eventType': 'performance',
                'visitorId': visitor_id,
                'sessionId': session_id,
                'timestamp': timestamp,
                'performance': {
                    'pageLoadTime': 1200,
                    'domContentLoaded': 600,
                    'firstByte': 150
                }
            })

            analytics = await get_analytics()

            assert analytics['summary']['totalPageviews'] == 1
            assert analytics['summary']['uniqueVisitors'] == 1
            assert analytics['summary']['uniqueSessions'] == 1
            assert analytics['summary']['avgScrollDepth'] == 80
            assert analytics['summary']['avgTimeOnPage'] == 45
            assert analytics['summary']['totalEvents'] == 5
            assert len(analytics['topClicks']) == 1
            assert analytics['avgPerformance']['pageLoadTime'] == 1200

    @pytest.mark.asyncio
    async def test_full_http_flow(self, temp_data_file):
        """Test complete HTTP flow: collect events then get analytics."""
        with patch('server.DATA_FILE', temp_data_file):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # Collect some events
                event = {
                    'eventType': 'pageview',
                    'visitorId': 'vis_http_test',
                    'sessionId': 'sess_http_test',
                    'timestamp': utc_now().isoformat().replace('+00:00', 'Z'),
                    'path': '/test-page',
                    'browser': 'Chrome',
                    'os': 'Windows',
                    'deviceType': 'Desktop'
                }

                response = await client.post("/collect", json=event)
                assert response.status_code == 200

                # Get analytics
                response = await client.get("/api/analytics")
                assert response.status_code == 200
                data = response.json()
                assert data['summary']['totalPageviews'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
