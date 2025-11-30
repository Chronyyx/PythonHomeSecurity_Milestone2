# Chart.js Integration - AnLex Guard Security Dashboard

## Overview
This document describes the Chart.js integration added to the AnLex Guard Security Dashboard to display historical sensor data from Adafruit IO.

## Changes Made

### 1. Frontend Changes (`templates/index.html`)

#### Added Libraries
- **Chart.js v4.4.0**: Main charting library
- **chartjs-adapter-date-fns**: Time scale adapter for Chart.js to handle datetime axes

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
```

#### New CSS Styles
- `.chart-container`: Responsive container for charts (300px height)
- `.date-selector`: Flexbox layout for date range controls
- Custom styling for date/datetime inputs to match the dark theme

#### New HTML Sections
Two new card sections added after the Sensors card:

1. **Temperature & Humidity Chart** (span-6)
   - Dual-axis line chart showing temperature (°C) and humidity (%)
   - Date range selector (from/to datetime-local inputs)
   - Update button to refresh chart data

2. **Motion Detection Chart** (span-6)
   - Bar chart showing motion event counts aggregated by hour
   - Date range selector (from/to datetime-local inputs)
   - Update button to refresh chart data

#### JavaScript Enhancements

**Global Variables:**
- `tempHumChart`: Chart.js instance for temperature/humidity
- `motionChart`: Chart.js instance for motion detection

**New Functions:**

1. `initializeDateSelectors()`
   - Sets default date range to last 24 hours
   - Formats datetime values for HTML5 datetime-local inputs

2. `initializeCharts()`
   - Creates Chart.js instances with dark theme configuration
   - Temperature/Humidity: Dual-axis line chart with time scale
   - Motion: Bar chart with hourly aggregation
   - Loads initial data for both charts

3. `updateTempHumChart()`
   - Fetches temperature and humidity data from backend API
   - Updates chart with new data points
   - Shows loading/success/error notifications

4. `updateMotionChart()`
   - Fetches motion detection events from backend API
   - Aggregates events by hour
   - Updates bar chart with event counts

### 2. Backend Changes

#### `app.py` - New API Endpoints

Three new Flask routes added to fetch historical data:

```python
@app.route('/api/history/temperature')
@app.route('/api/history/humidity')
@app.route('/api/history/motion')
```

Each endpoint:
- Accepts `start` and `end` query parameters (ISO datetime strings)
- Calls `AdafruitIOClient.get_data()` method
- Returns JSON response with data array

**Modified Endpoint:**
- `/api/status`: Updated to return structured JSON matching frontend expectations

#### `adafruit_io.py` - New Method

Added `get_data()` method to `AdafruitIOClient` class:

```python
def get_data(self, feed_key, start_time=None, end_time=None, limit=1000)
```

**Features:**
- Uses Adafruit IO REST API (not MQTT)
- Supports date range filtering
- Maximum 1000 data points per request (Adafruit IO limitation)
- Returns list of data points with `value` and `created_at` fields
- Handles authentication via `X-AIO-Key` header
- Error handling and logging

**Dependencies:**
- Added `requests` import (already in requirements.txt)
- Added `datetime` import for datetime handling

## Data Flow

```
User selects date range in UI
    ↓
Clicks "Update" button
    ↓
JavaScript calls /api/history/{sensor}?start=...&end=...
    ↓
Flask route calls system.aio_client.get_data(feed_key, start, end)
    ↓
AdafruitIOClient makes HTTPS GET request to io.adafruit.com REST API
    ↓
Data returned as JSON array
    ↓
Flask returns data to frontend
    ↓
Chart.js processes and displays data
```

## Chart Features

### Temperature & Humidity Chart
- **Type**: Line chart with dual Y-axes
- **Left Y-axis**: Temperature in °C (blue)
- **Right Y-axis**: Humidity in % (green)
- **X-axis**: Time scale with hourly intervals
- **Features**:
  - Smooth curves (tension: 0.4)
  - Semi-transparent fill under lines
  - Tooltips show both metrics at each time point
  - Responsive to container size

### Motion Detection Chart
- **Type**: Bar chart
- **Y-axis**: Count of motion events
- **X-axis**: Time scale with hourly intervals
- **Features**:
  - Events aggregated by hour
  - Yellow/gold color scheme matching warning theme
  - Integer step size on Y-axis
  - Responsive to container size

## Dark Theme Integration

Both charts use custom styling to match the AnLex Guard dark theme:
- Background: Transparent (inherits from card)
- Text color: `#e6edf3` (light gray)
- Muted text: `#8ea0b6` (medium gray)
- Grid lines: `rgba(33, 48, 70, 0.5)` (translucent)
- Tooltips: Dark background with border
- Brand colors: Temperature (blue), Humidity (green), Motion (yellow)

## Default Behavior

On page load:
1. Date selectors initialize to last 24 hours
2. Charts are created with empty datasets
3. Data is automatically loaded for the default 24-hour period
4. Charts display "Loading..." state during initial fetch

## User Interaction

Users can:
1. Select custom date ranges using datetime-local inputs
2. Click "Update" to refresh chart with new data
3. Hover over chart points to see detailed values
4. View charts that automatically resize with browser window

## Error Handling

- Network errors show notification to user
- Empty data sets display empty chart (no error)
- Backend errors logged and return empty array to prevent frontend crashes
- Adafruit IO API rate limits handled gracefully

## Future Enhancements

Potential improvements:
1. Auto-refresh charts on interval (like other dashboard data)
2. Export chart data to CSV
3. Zoom and pan controls for detailed analysis
4. Additional chart types (e.g., pie chart for alarm states)
5. Chart data caching to reduce API calls
6. Real-time data streaming (combine with polling)

## Testing

To test the charts:
1. Ensure Adafruit IO credentials are configured
2. Ensure data exists in the feeds (temperature, humidity, motion)
3. Access the dashboard at `http://localhost:5000`
4. Scroll to the chart sections
5. Verify charts load with 24-hour default data
6. Change date range and click Update
7. Verify charts update with new data

## Troubleshooting

**Charts not displaying:**
- Check browser console for JavaScript errors
- Verify Chart.js CDN is accessible
- Ensure canvas elements are present in DOM

**No data in charts:**
- Verify Adafruit IO feeds have data
- Check network tab for API response
- Verify date range includes data points
- Check backend logs for API errors

**Date selector issues:**
- Ensure browser supports `datetime-local` input type
- Check date format matches ISO 8601
- Verify timezone handling in backend

## Dependencies

**Frontend:**
- Chart.js 4.4.0
- chartjs-adapter-date-fns 3.0.0

**Backend:**
- requests >= 2.31.0 (already in requirements.txt)

## API Documentation

### GET /api/history/temperature
Fetch historical temperature data from Adafruit IO.

**Query Parameters:**
- `start` (optional): ISO 8601 datetime string
- `end` (optional): ISO 8601 datetime string

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "value": "23.5",
      "created_at": "2025-11-29T10:30:00Z"
    }
  ]
}
```

### GET /api/history/humidity
Fetch historical humidity data from Adafruit IO.

**Query Parameters:**
- `start` (optional): ISO 8601 datetime string
- `end` (optional): ISO 8601 datetime string

**Response:** Same format as temperature endpoint

### GET /api/history/motion
Fetch historical motion detection events from Adafruit IO.

**Query Parameters:**
- `start` (optional): ISO 8601 datetime string
- `end` (optional): ISO 8601 datetime string

**Response:** Same format as temperature endpoint

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-29  
**Author:** GitHub Copilot
