"""
Dolpyitcs - Analytics Server (FastAPI)
Collects and stores analytics data, serves the dashboard
"""

from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
import json
import os
import aiofiles
import structlog
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from contextlib import asynccontextmanager
import time

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("dolpyitcs")

# Metrics storage (in-memory for simplicity)
metrics = {
    "requests_total": 0,
    "events_collected": 0,
    "errors_total": 0,
    "request_duration_seconds": [],
    "startup_time": None,
}


def utc_now():
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan events."""
    metrics["startup_time"] = utc_now().isoformat()
    logger.info("server_started", port=PORT, pid=os.getpid())
    yield
    logger.info("server_stopped")


app = FastAPI(title="Dolpyitcs Analytics", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    metrics["requests_total"] += 1

    response = await call_next(request)

    duration = time.time() - start_time
    metrics["request_duration_seconds"].append(duration)
    # Keep only last 1000 durations
    if len(metrics["request_duration_seconds"]) > 1000:
        metrics["request_duration_seconds"] = metrics["request_duration_seconds"][-1000:]

    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
        client_ip=request.client.host if request.client else None,
    )

    return response

PORT = int(os.environ.get('PORT', 3000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)
DATA_FILE = os.path.join(DATA_DIR, 'analytics_data.json')


async def load_data():
    """Load analytics data from file."""
    if not os.path.exists(DATA_FILE):
        return {'events': []}
    try:
        async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return {'events': []}


async def save_data(data):
    """Save analytics data to file."""
    async with aiofiles.open(DATA_FILE, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(data, indent=2))


async def add_event(event):
    """Add a new event to the data store."""
    data = await load_data()
    event['receivedAt'] = utc_now().isoformat().replace('+00:00', 'Z')
    data['events'].append(event)
    metrics["events_collected"] += 1
    logger.debug("event_added", event_type=event.get('eventType'))

    # Keep only last 100,000 events
    if len(data['events']) > 100000:
        data['events'] = data['events'][-100000:]

    await save_data(data)


async def get_analytics(time_range='7d'):
    """Calculate analytics metrics for the given time range."""
    data = await load_data()
    now = utc_now().replace(tzinfo=None)  # Remove timezone for comparison

    # Calculate time range
    ranges = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        'all': None
    }

    range_delta = ranges.get(time_range, ranges['7d'])

    # Filter events by time range
    events = []
    for e in data['events']:
        try:
            event_time = datetime.fromisoformat(e.get('timestamp', '').replace('Z', ''))
            if range_delta is None or (now - event_time) <= range_delta:
                events.append(e)
        except (ValueError, TypeError):
            continue

    # Calculate metrics
    pageviews = [e for e in events if e.get('eventType') == 'pageview']
    unique_visitors = len(set(e.get('visitorId') for e in events if e.get('visitorId')))
    unique_sessions = len(set(e.get('sessionId') for e in events if e.get('sessionId')))

    # Pages breakdown
    pages_counts = defaultdict(int)
    for e in pageviews:
        page = e.get('path', '/')
        pages_counts[page] += 1
    top_pages = sorted(pages_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_pages = [{'page': p, 'views': v} for p, v in top_pages]

    # Referrers breakdown
    referrer_counts = defaultdict(int)
    for e in pageviews:
        ref = e.get('referrer', 'direct')
        if ref and ref != 'direct':
            try:
                from urllib.parse import urlparse
                ref = urlparse(ref).hostname or 'unknown'
            except Exception:
                ref = 'unknown'
        referrer_counts[ref] += 1
    top_referrers = sorted(referrer_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_referrers = [{'referrer': r, 'count': c} for r, c in top_referrers]

    # Browsers breakdown
    browser_counts = defaultdict(int)
    for e in pageviews:
        browser = e.get('browser', 'Unknown')
        browser_counts[browser] += 1
    browsers = sorted(browser_counts.items(), key=lambda x: x[1], reverse=True)
    browsers = [{'browser': b, 'count': c} for b, c in browsers]

    # OS breakdown
    os_counts = defaultdict(int)
    for e in pageviews:
        os_name = e.get('os', 'Unknown')
        os_counts[os_name] += 1
    operating_systems = sorted(os_counts.items(), key=lambda x: x[1], reverse=True)
    operating_systems = [{'os': o, 'count': c} for o, c in operating_systems]

    # Device types breakdown
    device_counts = defaultdict(int)
    for e in pageviews:
        device = e.get('deviceType', 'Unknown')
        device_counts[device] += 1
    devices = sorted(device_counts.items(), key=lambda x: x[1], reverse=True)
    devices = [{'device': d, 'count': c} for d, c in devices]

    # Timezones breakdown
    timezone_counts = defaultdict(int)
    for e in pageviews:
        tz = e.get('timezone', 'Unknown')
        timezone_counts[tz] += 1
    timezones = sorted(timezone_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    timezones = [{'timezone': t, 'count': c} for t, c in timezones]

    # Pageviews over time (daily)
    daily_views = defaultdict(int)
    for e in pageviews:
        try:
            date = e.get('timestamp', '')[:10]
            if date:
                daily_views[date] += 1
        except Exception:
            continue
    views_over_time = sorted(daily_views.items())
    views_over_time = [{'date': d, 'views': v} for d, v in views_over_time]

    # Average time on page
    time_on_page_events = [e for e in events if e.get('eventType') == 'time_on_page']
    avg_time_on_page = 0
    if time_on_page_events:
        total_time = sum(e.get('timeOnPage', 0) for e in time_on_page_events)
        avg_time_on_page = round(total_time / len(time_on_page_events))

    # Average scroll depth
    scroll_events = [e for e in events if e.get('eventType') == 'scroll_depth']
    avg_scroll_depth = 0
    if scroll_events:
        total_scroll = sum(e.get('maxScrollDepth', 0) for e in scroll_events)
        avg_scroll_depth = round(total_scroll / len(scroll_events))

    # Click events
    click_events = [e for e in events if e.get('eventType') == 'click']
    click_counts = defaultdict(int)
    for e in click_events:
        key = e.get('elementText') or e.get('elementId') or e.get('href') or 'Unknown'
        click_counts[key] += 1
    top_clicks = sorted(click_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_clicks = [{'element': el[:50], 'clicks': c} for el, c in top_clicks]

    # Errors
    errors = [e for e in events if e.get('eventType') == 'error']
    error_counts = defaultdict(int)
    for e in errors:
        msg = e.get('message', 'Unknown error')
        error_counts[msg] += 1
    top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_errors = [{'message': m[:100], 'count': c} for m, c in top_errors]

    # Performance metrics
    perf_events = [e for e in events if e.get('eventType') == 'performance' and e.get('performance')]
    avg_performance = None
    if perf_events:
        avg_performance = {
            'pageLoadTime': round(sum(e['performance'].get('pageLoadTime', 0) for e in perf_events) / len(perf_events)),
            'domContentLoaded': round(sum(e['performance'].get('domContentLoaded', 0) for e in perf_events) / len(perf_events)),
            'firstByte': round(sum(e['performance'].get('firstByte', 0) for e in perf_events) / len(perf_events))
        }

    # Recent events
    recent_events = []
    for e in events[-20:][::-1]:
        recent_events.append({
            'type': e.get('eventType'),
            'path': e.get('path'),
            'timestamp': e.get('timestamp'),
            'visitorId': (e.get('visitorId') or '')[:10],
            'browser': e.get('browser'),
            'device': e.get('deviceType')
        })

    return {
        'summary': {
            'totalPageviews': len(pageviews),
            'uniqueVisitors': unique_visitors,
            'uniqueSessions': unique_sessions,
            'avgTimeOnPage': avg_time_on_page,
            'avgScrollDepth': avg_scroll_depth,
            'totalEvents': len(events)
        },
        'topPages': top_pages,
        'topReferrers': top_referrers,
        'browsers': browsers,
        'operatingSystems': operating_systems,
        'devices': devices,
        'timezones': timezones,
        'viewsOverTime': views_over_time,
        'topClicks': top_clicks,
        'topErrors': top_errors,
        'avgPerformance': avg_performance,
        'recentEvents': recent_events
    }


# Routes

@app.get("/api/analytics")
async def analytics_endpoint(range: str = Query(default="7d")):
    """Get analytics data."""
    analytics = await get_analytics(range)
    return analytics


@app.get("/tracker.js")
async def serve_tracker():
    """Serve the tracker script."""
    tracker_path = os.path.join(BASE_DIR, 'public', 'tracker.js')
    if not os.path.exists(tracker_path):
        tracker_path = os.path.join(BASE_DIR, 'tracker.js')
    return FileResponse(tracker_path, media_type='application/javascript')


@app.get("/")
@app.get("/dashboard")
async def serve_dashboard():
    """Serve the dashboard HTML."""
    dashboard_path = os.path.join(BASE_DIR, 'dashboard.html')
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type='text/html')
    return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)


@app.post("/collect")
async def collect_event(request: Request):
    """Collect analytics events."""
    try:
        event = await request.json()
        # Add IP address
        event['ip'] = request.headers.get('X-Forwarded-For', request.client.host)
        await add_event(event)
        return {"success": True}
    except json.JSONDecodeError:
        metrics["errors_total"] += 1
        logger.warning("invalid_json_received", client_ip=request.client.host if request.client else None)
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": utc_now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/metrics")
async def get_metrics():
    """Prometheus-style metrics endpoint."""
    avg_duration = 0
    if metrics["request_duration_seconds"]:
        avg_duration = sum(metrics["request_duration_seconds"]) / len(metrics["request_duration_seconds"])

    return {
        "requests_total": metrics["requests_total"],
        "events_collected": metrics["events_collected"],
        "errors_total": metrics["errors_total"],
        "avg_request_duration_ms": round(avg_duration * 1000, 2),
        "uptime_since": metrics["startup_time"],
    }


if __name__ == '__main__':
    import uvicorn
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                    DOLPYITCS ANALYTICS                    ║
╠═══════════════════════════════════════════════════════════╣
║  Server running at: http://localhost:{PORT}                 ║
║  Dashboard:         http://localhost:{PORT}/dashboard       ║
║  Tracker script:    http://localhost:{PORT}/tracker.js      ║
║  API endpoint:      http://localhost:{PORT}/api/analytics   ║
║  API docs:          http://localhost:{PORT}/docs            ║
╚═══════════════════════════════════════════════════════════╝

Add this to your website's <head>:
<script src="http://localhost:{PORT}/tracker.js"></script>
    """)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
