"""
Dolpyitcs - Analytics Server (FastAPI + Prisma)
Collects and stores analytics data, serves the dashboard
"""

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import json
import os
import time
import structlog
from prisma import Prisma
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
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

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Add console exporter for development (can add Jaeger/OTLP for production)
span_processor = BatchSpanProcessor(ConsoleSpanExporter())
trace.get_tracer_provider().add_span_processor(span_processor)

# Prisma client
db = Prisma()

# Metrics storage (in-memory, complementing DB)
metrics = {
    "requests_total": 0,
    "events_collected": 0,
    "errors_total": 0,
    "db_queries": 0,
    "request_duration_seconds": [],
    "startup_time": None,
}


def utc_now():
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan events."""
    # Startup - try to connect to database, but don't fail if it's not available
    db_status = "disconnected"
    try:
        await db.connect()
        db_status = "connected"
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        db_status = f"failed: {str(e)[:50]}"

    metrics["startup_time"] = utc_now().isoformat()
    logger.info("server_started", port=PORT, pid=os.getpid(), database=db_status)

    yield

    # Shutdown
    try:
        if db.is_connected():
            await db.disconnect()
    except Exception:
        pass
    logger.info("server_stopped", database="disconnected")


app = FastAPI(
    title="Dolpyitcs Analytics",
    description="Privacy-friendly analytics platform",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

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
    """Log all requests with timing and tracing."""
    start_time = time.time()
    request_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000)}")

    # Bind request context to logger
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    metrics["requests_total"] += 1

    response = await call_next(request)

    duration = time.time() - start_time
    metrics["request_duration_seconds"].append(duration)
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

    response.headers["X-Request-ID"] = request_id
    return response


PORT = int(os.environ.get('PORT', 3000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Database operations
async def save_event(event_data: dict) -> str:
    """Save an event to the database."""
    with tracer.start_as_current_span("save_event") as span:
        span.set_attribute("event.type", event_data.get("eventType", "unknown"))

        metrics["db_queries"] += 1

        # Parse timestamp
        timestamp = event_data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                timestamp = utc_now()
        else:
            timestamp = utc_now()

        # Create event in database
        event = await db.event.create(
            data={
                "eventType": event_data.get("eventType", "unknown"),
                "visitorId": event_data.get("visitorId", ""),
                "sessionId": event_data.get("sessionId", ""),
                "timestamp": timestamp,
                "url": event_data.get("url"),
                "path": event_data.get("path"),
                "hostname": event_data.get("hostname"),
                "referrer": event_data.get("referrer"),
                "title": event_data.get("title"),
                "browser": event_data.get("browser"),
                "os": event_data.get("os"),
                "deviceType": event_data.get("deviceType"),
                "userAgent": event_data.get("userAgent"),
                "screenWidth": event_data.get("screenWidth"),
                "screenHeight": event_data.get("screenHeight"),
                "viewportWidth": event_data.get("viewportWidth"),
                "viewportHeight": event_data.get("viewportHeight"),
                "colorDepth": event_data.get("colorDepth"),
                "language": event_data.get("language"),
                "timezone": event_data.get("timezone"),
                "timezoneOffset": event_data.get("timezoneOffset"),
                "ip": event_data.get("ip"),
                "data": json.dumps(event_data) if event_data else None,
            }
        )

        # Update visitor record
        await db.visitor.upsert(
            where={"visitorId": event_data.get("visitorId", "")},
            data={
                "create": {
                    "visitorId": event_data.get("visitorId", ""),
                    "totalEvents": 1,
                },
                "update": {
                    "lastSeen": utc_now(),
                    "totalEvents": {"increment": 1},
                },
            }
        )

        # Update session record
        await db.session.upsert(
            where={"sessionId": event_data.get("sessionId", "")},
            data={
                "create": {
                    "sessionId": event_data.get("sessionId", ""),
                    "visitorId": event_data.get("visitorId", ""),
                    "entryPage": event_data.get("path"),
                    "browser": event_data.get("browser"),
                    "os": event_data.get("os"),
                    "deviceType": event_data.get("deviceType"),
                    "pageviews": 1 if event_data.get("eventType") == "pageview" else 0,
                    "events": 1,
                },
                "update": {
                    "endedAt": utc_now(),
                    "exitPage": event_data.get("path"),
                    "pageviews": {"increment": 1 if event_data.get("eventType") == "pageview" else 0},
                    "events": {"increment": 1},
                },
            }
        )

        # Save performance data if present
        if event_data.get("eventType") == "performance" and event_data.get("performance"):
            perf = event_data["performance"]
            await db.pageperformance.create(
                data={
                    "eventId": event.id,
                    "path": event_data.get("path", "/"),
                    "timestamp": timestamp,
                    "pageLoadTime": perf.get("pageLoadTime"),
                    "domContentLoaded": perf.get("domContentLoaded"),
                    "firstByte": perf.get("firstByte"),
                    "dnsLookup": perf.get("dnsLookup"),
                    "tcpConnect": perf.get("tcpConnect"),
                }
            )

        # Save error data if present
        if event_data.get("eventType") == "error":
            await db.error.create(
                data={
                    "eventId": event.id,
                    "visitorId": event_data.get("visitorId", ""),
                    "sessionId": event_data.get("sessionId", ""),
                    "timestamp": timestamp,
                    "message": event_data.get("message", "Unknown error"),
                    "source": event_data.get("source"),
                    "line": event_data.get("line"),
                    "column": event_data.get("colno"),
                    "stack": event_data.get("stack"),
                    "path": event_data.get("path"),
                    "browser": event_data.get("browser"),
                    "os": event_data.get("os"),
                }
            )

        metrics["events_collected"] += 1
        logger.debug("event_saved", event_id=event.id, event_type=event_data.get("eventType"))

        return event.id


async def get_analytics(time_range: str = '7d', hostname: str = None):
    """Get analytics data from database."""
    with tracer.start_as_current_span("get_analytics") as span:
        span.set_attribute("time_range", time_range)

        metrics["db_queries"] += 1
        now = utc_now()

        # Calculate time range
        ranges = {
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30),
            'all': None
        }
        range_delta = ranges.get(time_range, ranges['7d'])

        start_time = (now - range_delta) if range_delta else None

        # Build where clause
        where = {}
        if start_time:
            where["timestamp"] = {"gte": start_time}
        if hostname:
            where["hostname"] = hostname

        # Get pageviews
        pageviews = await db.event.count(
            where={**where, "eventType": "pageview"}
        )

        # Get unique visitors
        visitors_result = await db.event.find_many(
            where=where,
            distinct=["visitorId"]
        )
        unique_visitors = len(visitors_result)

        # Get unique sessions
        sessions_result = await db.event.find_many(
            where=where,
            distinct=["sessionId"]
        )
        unique_sessions = len(sessions_result)

        # Get top pages
        top_pages_raw = await db.event.group_by(
            by=["path"],
            where={**where, "eventType": "pageview"},
            count={"path": True},
            order={"_count": {"path": "desc"}},
            take=10
        )
        top_pages = [{"page": getattr(p, "path", None) or "/", "views": getattr(p, "_count", {}).get("path", 0)} for p in top_pages_raw]

        # Get browsers
        browsers_raw = await db.event.group_by(
            by=["browser"],
            where={**where, "eventType": "pageview"},
            count={"browser": True},
            order={"_count": {"browser": "desc"}}
        )
        browsers = [{"browser": getattr(b, "browser", None) or "Unknown", "count": getattr(b, "_count", {}).get("browser", 0)} for b in browsers_raw]

        # Get devices
        devices_raw = await db.event.group_by(
            by=["deviceType"],
            where={**where, "eventType": "pageview"},
            count={"deviceType": True},
            order={"_count": {"deviceType": "desc"}}
        )
        devices = [{"device": getattr(d, "deviceType", None) or "Unknown", "count": getattr(d, "_count", {}).get("deviceType", 0)} for d in devices_raw]

        # Get OS
        os_raw = await db.event.group_by(
            by=["os"],
            where={**where, "eventType": "pageview"},
            count={"os": True},
            order={"_count": {"os": "desc"}}
        )
        operating_systems = [{"os": getattr(o, "os", None) or "Unknown", "count": getattr(o, "_count", {}).get("os", 0)} for o in os_raw]

        # Get referrers
        referrers_raw = await db.event.group_by(
            by=["referrer"],
            where={**where, "eventType": "pageview"},
            count={"referrer": True},
            order={"_count": {"referrer": "desc"}},
            take=10
        )
        top_referrers = [{"referrer": getattr(r, "referrer", None) or "direct", "count": getattr(r, "_count", {}).get("referrer", 0)} for r in referrers_raw]

        # Get recent events
        recent_events_raw = await db.event.find_many(
            where=where,
            order={"timestamp": "desc"},
            take=20
        )
        recent_events = [
            {
                "type": e.eventType,
                "path": e.path,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "visitorId": e.visitorId[:10] if e.visitorId else "",
                "browser": e.browser,
                "device": e.deviceType,
            }
            for e in recent_events_raw
        ]

        # Get average performance
        perf_data = await db.pageperformance.aggregate(
            where={"timestamp": {"gte": start_time}} if start_time else {},
            _avg={
                "pageLoadTime": True,
                "domContentLoaded": True,
                "firstByte": True,
            }
        )
        avg_performance = None
        if perf_data and perf_data._avg:
            avg_obj = perf_data._avg
            avg_performance = {
                "pageLoadTime": round(getattr(avg_obj, "pageLoadTime", None) or 0),
                "domContentLoaded": round(getattr(avg_obj, "domContentLoaded", None) or 0),
                "firstByte": round(getattr(avg_obj, "firstByte", None) or 0),
            }

        # Get errors
        errors_raw = await db.error.group_by(
            by=["message"],
            where={"timestamp": {"gte": start_time}} if start_time else {},
            count={"message": True},
            order={"_count": {"message": "desc"}},
            take=5
        )
        top_errors = [{"message": (getattr(e, "message", "") or "")[:100], "count": getattr(e, "_count", {}).get("message", 0)} for e in errors_raw]

        # Total events
        total_events = await db.event.count(where=where)

        return {
            "summary": {
                "totalPageviews": pageviews,
                "uniqueVisitors": unique_visitors,
                "uniqueSessions": unique_sessions,
                "totalEvents": total_events,
                "avgTimeOnPage": 0,  # TODO: Calculate from session data
                "avgScrollDepth": 0,  # TODO: Calculate from events
            },
            "topPages": top_pages,
            "topReferrers": top_referrers,
            "browsers": browsers,
            "operatingSystems": operating_systems,
            "devices": devices,
            "timezones": [],  # TODO: Add timezone grouping
            "viewsOverTime": [],  # TODO: Add time series data
            "topClicks": [],  # TODO: Add click tracking
            "topErrors": top_errors,
            "avgPerformance": avg_performance,
            "recentEvents": recent_events,
        }


# Routes

@app.get("/api/analytics")
async def analytics_endpoint(
    range: str = Query(default="7d", description="Time range: 24h, 7d, 30d, all"),
    hostname: str = Query(default=None, description="Filter by hostname")
):
    """Get analytics data."""
    try:
        analytics = await get_analytics(range, hostname)
        return analytics
    except Exception as e:
        logger.error("analytics_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch analytics")


@app.get("/tracker.js")
async def serve_tracker():
    """Serve the tracker script."""
    tracker_path = os.path.join(BASE_DIR, 'public', 'tracker.js')
    if not os.path.exists(tracker_path):
        tracker_path = os.path.join(BASE_DIR, 'tracker.js')
    if os.path.exists(tracker_path):
        return FileResponse(tracker_path, media_type='application/javascript')
    raise HTTPException(status_code=404, detail="Tracker not found")


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
        event['ip'] = request.headers.get('X-Forwarded-For', request.client.host if request.client else None)

        # Save to database
        event_id = await save_event(event)

        return {"success": True, "eventId": event_id}
    except json.JSONDecodeError:
        metrics["errors_total"] += 1
        logger.warning("invalid_json_received", client_ip=request.client.host if request.client else None)
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    except Exception as e:
        metrics["errors_total"] += 1
        logger.error("collect_error", error=str(e))
        return JSONResponse({"error": "Failed to save event"}, status_code=500)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    db_status = "connected" if db.is_connected() else "disconnected"
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": utc_now().isoformat(),
        "version": "1.0.0",
        "database": db_status,
    }


@app.get("/metrics")
async def get_metrics_endpoint():
    """Prometheus-style metrics endpoint."""
    avg_duration = 0
    if metrics["request_duration_seconds"]:
        avg_duration = sum(metrics["request_duration_seconds"]) / len(metrics["request_duration_seconds"])

    # Get database stats
    total_events = 0
    total_visitors = 0
    total_sessions = 0
    try:
        total_events = await db.event.count()
        total_visitors = await db.visitor.count()
        total_sessions = await db.session.count()
    except Exception:
        pass

    return {
        "requests_total": metrics["requests_total"],
        "events_collected": metrics["events_collected"],
        "errors_total": metrics["errors_total"],
        "db_queries": metrics["db_queries"],
        "avg_request_duration_ms": round(avg_duration * 1000, 2),
        "uptime_since": metrics["startup_time"],
        "database": {
            "total_events": total_events,
            "total_visitors": total_visitors,
            "total_sessions": total_sessions,
        }
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
║  Health check:      http://localhost:{PORT}/health          ║
║  Metrics:           http://localhost:{PORT}/metrics         ║
╚═══════════════════════════════════════════════════════════╝

Make sure DATABASE_URL is set in your environment!
    """)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
