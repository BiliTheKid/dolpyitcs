# Dolpyitcs - Simple Analytics

A lightweight, self-hosted analytics solution similar to Google Analytics.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the server:**
   ```bash
   python server.py
   ```

3. **Add tracking to your website:**
   ```html
   <script src="http://localhost:3000/tracker.js"></script>
   ```

4. **View your dashboard:**
   Open http://localhost:3000 in your browser

## Running Tests

```bash
python -m pytest test_server.py -v
```

## What It Tracks

### Automatic Tracking
- **Page Views** - Every page visit with URL, title, referrer
- **Unique Visitors** - Persistent visitor ID stored in localStorage
- **Sessions** - Session tracking via sessionStorage
- **Device Info** - Browser, OS, device type (mobile/desktop/tablet)
- **Screen Size** - Screen resolution and viewport dimensions
- **Timezone** - User's timezone and language
- **Performance** - Page load time, DOM ready time, time to first byte
- **Scroll Depth** - How far users scroll down the page
- **Time on Page** - How long users spend on each page
- **Clicks** - Tracks clicks on links, buttons, and elements with `data-track`
- **Form Submissions** - Tracks when forms are submitted
- **JavaScript Errors** - Captures client-side errors

### Custom Events
Track custom events in your code:
```javascript
// Track a custom event
dolpyitcs.track('purchase', {
  product: 'T-Shirt',
  price: 29.99,
  currency: 'USD'
});

// Identify a user
dolpyitcs.identify('user123', {
  name: 'John Doe',
  email: 'john@example.com',
  plan: 'premium'
});
```

### Data-Track Attribute
Add `data-track` to elements for automatic click tracking with custom names:
```html
<button data-track="signup-button">Sign Up</button>
<a href="/pricing" data-track="pricing-link">View Pricing</a>
```

## Dashboard Features

- **Real-time updates** - Auto-refreshes every 30 seconds
- **Time filters** - View data for 24h, 7 days, 30 days, or all time
- **Key metrics** - Pageviews, unique visitors, sessions, avg time on page
- **Top pages** - Most visited pages
- **Referrers** - Where your traffic comes from
- **Browser & OS breakdown** - What devices your users have
- **Click tracking** - Most clicked elements
- **Error tracking** - JavaScript errors on your site
- **Performance metrics** - Average page load times
- **Recent events** - Live feed of recent activity

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/collect` | POST | Receives tracking data |
| `/api/analytics` | GET | Returns analytics data |
| `/tracker.js` | GET | Serves the tracking script |
| `/` | GET | Serves the dashboard |

### Query Parameters for `/api/analytics`
- `range` - Time range: `24h`, `7d`, `30d`, `all` (default: `7d`)

## Configuration

### Changing the Server Port
Edit `server.py` and change the `PORT` constant.

### Tracking a Different Server
Edit `tracker.js` and change `ANALYTICS_ENDPOINT` to your server URL.

### Production Deployment
For production, you should:
1. Use HTTPS
2. Set proper CORS headers for your domain
3. Consider using a database instead of JSON file storage
4. Add authentication to the dashboard

## File Structure

```
dolpyitcs/
├── server.py          # Backend server (Python)
├── tracker.js         # Client-side tracking snippet
├── dashboard.html     # Analytics dashboard
├── test_server.py     # Test suite
├── requirements.txt   # Python dependencies
├── analytics_data.json # Data storage (auto-created)
└── README.md          # This file
```

## License

MIT - Use it however you want!
