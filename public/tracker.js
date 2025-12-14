/**
 * Dolpyitcs - Simple Analytics Tracker
 * Embed this snippet on your website to track user behavior
 */
(function() {
  'use strict';

  // Configuration - UPDATE THIS to your Fly.io URL after deployment!
  // Example: 'https://dolpyitcs.fly.dev/collect'
  const ANALYTICS_ENDPOINT = 'https://dolpyitcs.fly.dev/collect';

  // Generate or retrieve session ID
  function getSessionId() {
    let sessionId = sessionStorage.getItem('_dolpyitcs_session');
    if (!sessionId) {
      sessionId = 'sess_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
      sessionStorage.setItem('_dolpyitcs_session', sessionId);
    }
    return sessionId;
  }

  // Generate or retrieve visitor ID (persistent)
  function getVisitorId() {
    let visitorId = localStorage.getItem('_dolpyitcs_visitor');
    if (!visitorId) {
      visitorId = 'vis_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
      localStorage.setItem('_dolpyitcs_visitor', visitorId);
    }
    return visitorId;
  }

  // Get device and browser info
  function getDeviceInfo() {
    const ua = navigator.userAgent;

    // Detect browser
    let browser = 'Unknown';
    if (ua.includes('Firefox')) browser = 'Firefox';
    else if (ua.includes('Edg')) browser = 'Edge';
    else if (ua.includes('Chrome')) browser = 'Chrome';
    else if (ua.includes('Safari')) browser = 'Safari';
    else if (ua.includes('Opera') || ua.includes('OPR')) browser = 'Opera';

    // Detect OS
    let os = 'Unknown';
    if (ua.includes('Windows')) os = 'Windows';
    else if (ua.includes('Mac')) os = 'macOS';
    else if (ua.includes('Linux')) os = 'Linux';
    else if (ua.includes('Android')) os = 'Android';
    else if (ua.includes('iOS') || ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS';

    // Detect device type
    let deviceType = 'Desktop';
    if (/Mobi|Android/i.test(ua)) deviceType = 'Mobile';
    else if (/Tablet|iPad/i.test(ua)) deviceType = 'Tablet';

    return { browser, os, deviceType, userAgent: ua };
  }

  // Get page performance metrics
  function getPerformanceMetrics() {
    if (!window.performance || !window.performance.timing) return null;

    const timing = window.performance.timing;
    return {
      pageLoadTime: timing.loadEventEnd - timing.navigationStart,
      domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
      firstByte: timing.responseStart - timing.navigationStart,
      dnsLookup: timing.domainLookupEnd - timing.domainLookupStart,
      tcpConnect: timing.connectEnd - timing.connectStart
    };
  }

  // Core tracking data
  function getBaseData() {
    return {
      visitorId: getVisitorId(),
      sessionId: getSessionId(),
      timestamp: new Date().toISOString(),
      url: window.location.href,
      path: window.location.pathname,
      hostname: window.location.hostname,
      referrer: document.referrer || 'direct',
      title: document.title,
      language: navigator.language,
      screenWidth: window.screen.width,
      screenHeight: window.screen.height,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      colorDepth: window.screen.colorDepth,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      timezoneOffset: new Date().getTimezoneOffset(),
      ...getDeviceInfo()
    };
  }

  // Send data to server
  function sendData(eventType, eventData = {}) {
    const payload = {
      eventType,
      ...getBaseData(),
      ...eventData
    };

    // Use sendBeacon for reliability (won't be cancelled on page unload)
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ANALYTICS_ENDPOINT, JSON.stringify(payload));
    } else {
      // Fallback to fetch
      fetch(ANALYTICS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true
      }).catch(() => {});
    }
  }

  // Track page view
  function trackPageView() {
    sendData('pageview');
  }

  // Track page view with performance data (after page load)
  function trackPageViewWithPerformance() {
    const performance = getPerformanceMetrics();
    if (performance && performance.pageLoadTime > 0) {
      sendData('performance', { performance });
    }
  }

  // Track clicks
  function trackClicks(event) {
    const target = event.target.closest('a, button, [data-track]');
    if (!target) return;

    const data = {
      elementType: target.tagName.toLowerCase(),
      elementId: target.id || null,
      elementClass: target.className || null,
      elementText: target.innerText?.substring(0, 100) || null,
      href: target.href || null,
      dataTrack: target.dataset.track || null
    };

    sendData('click', data);
  }

  // Track scroll depth
  let maxScrollDepth = 0;
  function trackScroll() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const scrollPercent = Math.round((scrollTop / docHeight) * 100);

    if (scrollPercent > maxScrollDepth) {
      maxScrollDepth = scrollPercent;
    }
  }

  // Send scroll depth on page leave
  function sendScrollDepth() {
    if (maxScrollDepth > 0) {
      sendData('scroll_depth', { maxScrollDepth });
    }
  }

  // Track time on page
  const pageStartTime = Date.now();
  function sendTimeOnPage() {
    const timeOnPage = Math.round((Date.now() - pageStartTime) / 1000);
    sendData('time_on_page', { timeOnPage });
  }

  // Track form submissions
  function trackFormSubmit(event) {
    const form = event.target;
    if (form.tagName !== 'FORM') return;

    sendData('form_submit', {
      formId: form.id || null,
      formAction: form.action || null,
      formMethod: form.method || null
    });
  }

  // Track errors
  function trackError(event) {
    sendData('error', {
      message: event.message,
      source: event.filename,
      line: event.lineno,
      column: event.colno,
      stack: event.error?.stack?.substring(0, 500) || null
    });
  }

  // Track visibility changes (tab focus/blur)
  let hiddenTime = 0;
  let hiddenStart = null;
  function trackVisibility() {
    if (document.hidden) {
      hiddenStart = Date.now();
    } else if (hiddenStart) {
      hiddenTime += Date.now() - hiddenStart;
      hiddenStart = null;
    }
  }

  // Custom event tracking (exposed globally)
  const api = {
    track: function(eventName, data = {}) {
      sendData('custom', { eventName, customData: data });
    },
    identify: function(userId, traits = {}) {
      localStorage.setItem('_dolpyitcs_user', userId);
      sendData('identify', { userId, traits });
    }
  };

  // Process any queued events from the loader
  function processQueue() {
    const queued = window.dolpyitcs?.q || [];
    queued.forEach(function(args) {
      const method = args[0];
      const params = Array.from(args[1]);
      if (api[method]) {
        api[method].apply(null, params);
      }
    });
  }

  // Expose API globally
  window.dolpyitcs = api;

  // Initialize tracking
  function init() {
    // Process any events queued before script loaded
    processQueue();

    // Track initial page view
    trackPageView();

    // Track performance after page load
    window.addEventListener('load', function() {
      setTimeout(trackPageViewWithPerformance, 100);
    });

    // Track clicks
    document.addEventListener('click', trackClicks, true);

    // Track scroll
    window.addEventListener('scroll', trackScroll, { passive: true });

    // Track form submissions
    document.addEventListener('submit', trackFormSubmit, true);

    // Track JavaScript errors
    window.addEventListener('error', trackError);

    // Track visibility changes
    document.addEventListener('visibilitychange', trackVisibility);

    // Send final data before page unload
    window.addEventListener('beforeunload', function() {
      sendScrollDepth();
      sendTimeOnPage();
    });

    // Also use pagehide for mobile browsers
    window.addEventListener('pagehide', function() {
      sendScrollDepth();
      sendTimeOnPage();
    });
  }

  // Start tracking when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
