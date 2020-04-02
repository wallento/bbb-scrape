# Scrape Big Blue Button (BBB) meeting

Scrape a BBB meeting. Currently only supports:

 - Extract slides and create video with proper timing
 - Download desk sharing and webcam videos if present
 - Render slide annotations and polls

Upcoming features:

 - Render new video with combined elements
 - Render chat

Installation:

```
pip install bbb-scrape
```

You also need inkscape installed (image conversion in the background).

Use:

```
bbb-scrape <hostname> <meetingid>
```
