# Village Pond Planning System - YouTube Demo Script
**Target Length:** 4.5 to 5 minutes

## General Instructions for Recording:
- **Pacing:** Speak clearly and at a moderate pace. Pause slightly between sections.
- **Screen:** Have the web application (`http://10.1.75.53:5205/app/`) already open in your browser, along with a sample KML file ready to upload.
- **Audio:** Ensure you are in a quiet room and using a good microphone if possible.

---

## Script and Screen Actions

### 1. Introduction (0:00 - 0:45)
**Screen Action:** Start with the homepage/map view of the web application. Show the main interface.
**Script:**
> "Hello everyone, my name is Avinash Patel. Today I am demonstrating the 'AI-based Village Pond Planning System', developed for my Cloud Software Development lab assignment. The goal of this project is to automate the complex process of identifying optimal locations for rainwater harvesting ponds in rural areas. Instead of relying on manual surveys, our system uses topographical analysis, hydrological modeling, and digital elevation data to recommend the best sites, calculate catchment areas, and estimate water volume."

### 2. Architecture and Algorithm Overview (0:45 - 2:00)
**Screen Action:** Briefly switch to a slide or an image of the Architecture Diagram (`architecture.png` that we generated).
**Script:**
> "Before we see it in action, let me briefly explain how it works under the hood. The system is built with a React frontend and a FastAPI backend in Python, all hosted on a remote Ubuntu server.
> 
> The core algorithm relies on a geospatial pipeline using libraries like `pysheds` and `rasterio`. When an area is selected or a contour map is uploaded, the system does the following:
> First, it builds a Digital Elevation Model—or DEM—grid from local SRTM height tiles.
> Second, it runs a D8 flow routing algorithm to calculate flow direction and flow accumulation. This tells us where the water naturally gathers.
> Third, it computes slope and excludes areas that are too steep, as well as existing rivers or water bodies.
> Finally, it ranks the candidate points based on high flow accumulation and low slope, delineates the catchment basin for the best sites, and uses the Rational Method to estimate the potential water volume."

### 3. Demo - Bounding Box Analysis (2:00 - 3:15)
**Screen Action:** Switch back to the web application. Zoom into a rural area (like Chhattisgarh). Click the "Draw Rectangle" tool and draw a small bounding box (around 5km x 5km or 0.05 deg x 0.05 deg). Click "Analyze Area". While it loads, keep talking.
**Script:**
> "Let's see a live demonstration. There are two ways to use the system. The first is by simply drawing a bounding box on the map over a region of interest. I'll select an area here in Chhattisgarh. 
> 
> When I click 'Analyze', the frontend sends the coordinates to the backend. The backend fetches the 30-meter resolution SRTM elevation data for this specific area from our local server cache, and runs the hydrological pipeline I just described.
> 
> *(Wait for results to appear)*
> 
> As you can see, the results have loaded. The blue polygon represents the delineated catchment area—the exact region where rainfall will flow into our pond. The markers indicate the top three recommended pond sites, ranked by suitability. On the right panel, we can see the exact area in square kilometers, the estimated annual runoff, and the recommended storage volume for the primary pond."

### 4. Demo - KML Upload (3:15 - 4:15)
**Screen Action:** Switch to the "Upload Contour File" tab on the left panel. Select a sample `.kml` or `.kmz` file from your computer and upload it.
**Script:**
> "The second method is uploading a custom contour map, which is highly useful if you have specific survey data or drone-generated KML files. 
> 
> I will switch to the Upload tab and select a KML file. The system parses the geometric boundaries from this file to determine the region, and then performs the same rigorous terrain and flow accumulation analysis. 
> 
> *(Wait for results to appear)*
> 
> Once again, it successfully identifies the pour points, traces the catchment boundaries, and provides us with actionable metrics for pond construction in this specific surveyed area."

### 5. Conclusion (4:15 - 4:45)
**Screen Action:** Pan around the 3D map slightly, click on one of the markers to show the popup details, and then return to a full view of the map.
**Script:**
> "To summarize, this system significantly reduces the time and cost required for water resource planning. By combining modern web technologies with robust geospatial algorithms, we can provide immediate, data-driven recommendations for sustainable water management in rural communities. 
> 
> Thank you for watching this demonstration."
