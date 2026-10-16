# 🎓 Viva Preparation — EASY VERSION

> Read this FIRST. It explains everything in simple language.  
> After this makes sense, glance at `viva.md` for deeper details.

---

## Part 1: What Does Your Project Actually Do?

### The Real-World Problem

Imagine a village that needs a pond to collect rainwater. Where should they dig it?

- **Not on a hilltop** — water runs away from hilltops
- **Not in a river** — it's already a river, and floods will destroy your pond
- **In a natural bowl/depression** where water from surrounding hills flows INTO — that's the sweet spot

Traditionally, an experienced engineer walks around the village land, looks at the terrain, and says "dig here." That's expensive and slow.

**Your project does the same thing, but from a computer.** It uses satellite elevation data (how high/low each point of land is) to figure out where water would naturally flow, and recommends the best spot to build a pond.

### What the User Does

1. Opens a website in their browser
2. Sees a map (like Google Maps)
3. Draws a rectangle on the map around the area they want to analyze
4. Waits ~1 minute
5. Gets back: "Here are the 3 best spots to build a pond, ranked by suitability"

---

## Part 2: Glossary — Every Term You Need to Know

Read this section carefully. **Every scary word** in the project is explained here in plain English.

### Geography & Data Terms

| Term | Simple Explanation |
|------|-------------------|
| **DEM** (Digital Elevation Model) | A grid of numbers where each number is the height of that spot above sea level. Think of it as a spreadsheet where each cell contains an elevation value like "312 meters." |
| **SRTM** (Shuttle Radar Topography Mission) | A NASA space shuttle mission that scanned the entire Earth and measured how high every point is. The data is free to download. Your project uses this data. |
| **`.hgt` file** | The file format SRTM data comes in. Each file covers a 1° × 1° area (roughly 111 km × 111 km). It's basically a big grid of height numbers. |
| **30m resolution** | Each "pixel" in the elevation data covers a 30m × 30m patch of ground. So the system can't see features smaller than ~30 meters. |
| **Contour line** | A line on a map connecting points of equal elevation. Like the lines you see on a hiking/trekking map. All points on the same contour line are at the same height. |
| **KML/KMZ** | File formats for geographic data (used by Google Earth). Your project can accept these as input instead of drawing a rectangle. |
| **Bounding box (bbox)** | Just a rectangle defined by 4 numbers: west, south, east, north (the edges). When the user draws a rectangle on the map, those 4 coordinates are the bounding box. |
| **WGS84** | The coordinate system used by GPS. Locations are expressed as latitude/longitude in degrees. Your project uses this. |
| **GeoJSON** | A standard format for representing geographic shapes (polygons, points, lines) as JSON. The backend sends results in this format so the map can display them. |

### Water & Hydrology Terms

| Term | Simple Explanation |
|------|-------------------|
| **Hydrology** | The science of how water moves across land. Your project simulates this. |
| **Flow direction** | Which way would water flow from each point? Downhill, obviously — but exactly which direction? That's what flow direction calculates. |
| **D8 algorithm** | The specific method used. For each point on the grid, look at 8 neighbors (N, NE, E, SE, S, SW, W, NW). Water flows toward whichever neighbor is MOST downhill (steepest drop). Simple concept, just formalized. |
| **Flow accumulation** | How much water passes through each point? A hilltop gets only its own rain (accumulation = 1). A river valley gets water from thousands of upstream points (accumulation = 10,000+). |
| **Drainage channel** | Where accumulation is very high = a stream or river. Your project identifies these so it DOESN'T put a pond there. |
| **Catchment area** | The entire region of land that drains water into a specific point. If you pour water anywhere in the catchment, it eventually flows to that point. Also called "watershed" or "drainage basin." |
| **Pour point** | The specific point where all the water from the catchment exits. Think of it as the "drain hole" of the catchment basin. |
| **Runoff** | Rain that doesn't soak into the ground — it flows across the surface. A fraction of rainfall becomes runoff (your project uses 35%). |
| **Runoff coefficient (C = 0.35)** | 35% of rain becomes runoff (flows across surface), 65% soaks into the ground. This is a reasonable estimate for mixed farmland/forest. |
| **Sink/Pit** | A low point on the terrain where water gets trapped (like a pothole). Usually caused by errors in the data, not real features. Must be "filled" (raised) before the flow algorithm works. |
| **Rational Method** | The formula: `Water Volume = Area × Rainfall × Runoff Coefficient`. Simple multiplication — nothing complicated. |

### Computer Science & Architecture Terms

| Term | Simple Explanation |
|------|-------------------|
| **FastAPI** | The Python web framework used. It receives HTTP requests from the browser and sends back JSON responses. Like Flask but faster and with automatic documentation. |
| **Uvicorn** | The actual server program that runs FastAPI. Think of it as the engine that makes FastAPI accessible on the network. |
| **ASGI / Async** | A way of handling multiple requests without blocking. The server doesn't freeze while waiting for things — it can handle other requests in the meantime. |
| **Event loop** | The core of async programming. It's like a manager that keeps checking: "Any new requests? Any finished tasks?" and handles them one by one, very fast. |
| **Thread pool** | A set of worker threads. When the event loop has heavy work (like computing terrain analysis for 60 seconds), it hands the work to a thread so the event loop stays free. |
| **Mutex / Lock** | A "one at a time" rule. Like a bathroom lock — only one person can use it. In our code, only one analysis runs at a time to prevent running out of memory. |
| **HTTP 429** | "Too Many Requests" error. If someone tries to start a second analysis while one is running, they get this error saying "wait and try again." |
| **cgroup** | Linux feature that limits how much memory a process can use. Your lab machines limit each student to 512 MB of RAM. |
| **OOM kill** | "Out Of Memory" — when a process tries to use more than the cgroup allows, Linux forcibly kills it (SIGKILL). |
| **Redis** | A super-fast in-memory database used for caching. Stores key-value pairs in RAM. Your project uses it to remember results so the same query doesn't need to recompute. |
| **TTL (Time To Live)** | How long a cached result stays valid. Your project uses 24 hours — after that, the cached result expires and would need to be recomputed. |
| **Cache hit / miss** | Hit = the result was found in cache (fast, <50ms). Miss = not in cache, must compute from scratch (slow, 60-120s). |
| **Load balancer (LB)** | A program that distributes incoming requests across multiple servers. Like a receptionist directing patients to different doctors. |
| **Round-robin** | The simplest LB strategy: send request 1 to server A, request 2 to server B, request 3 to server A, request 4 to server B, ... repeat. |
| **Health check** | The LB periodically asks each server "are you alive?" (`GET /health`). If a server doesn't respond, the LB stops sending it requests. |
| **Failover** | When one server dies, traffic automatically goes to the surviving server(s). |
| **Stateless** | Each server has no memory of previous requests. Any server can handle any request. This is what makes load balancing work. |
| **Monolith** | One big application (as opposed to microservices). Your project is a monolith — all the code runs in one process. |
| **CORS** | Cross-Origin Resource Sharing — a browser security rule. Your backend has it configured to allow the frontend to talk to it. |
| **REST API** | A way of designing web APIs using HTTP methods (GET, POST, etc.) and URLs. Your project uses REST. |
| **Pydantic** | A Python library for data validation. Ensures that when someone sends `{"west": 81.25, ...}`, the values are actually numbers. |

### Library Names

| Library | What It Does (Simple) |
|---------|---------------------|
| **NumPy** | Math with big arrays of numbers. Your elevation grid is a NumPy array. |
| **SciPy** | Scientific computing tools. Used for interpolation (filling gaps in data) and image-like operations on the grid. |
| **pysheds** | Hydrology toolkit. Does the heavy lifting: fill pits, compute flow direction, compute flow accumulation. |
| **Rasterio** | Reads/writes geographic image files (GeoTIFF format). Needed to feed data into pysheds. |
| **Shapely** | Creates and manipulates geometric shapes (polygons, points). Used to build the catchment boundary polygon. |
| **pyproj** | Converts between coordinate systems. Used to calculate area in square meters (not in degrees). |
| **lxml** | Parses XML/KML files. Used to read uploaded contour maps. |
| **httpx** | Async HTTP client. Used by the load balancer to forward requests to backend servers. |
| **React** | JavaScript library for building user interfaces. The frontend is built with React. |
| **Leaflet** | JavaScript library for interactive maps. The map you see in the browser is Leaflet. |

---

## Part 3: How the System Works — Step by Step (Simple Version)

Think of it as a **recipe with 7 steps**:

### Step 1: User Draws a Rectangle 📐

User draws a box on the map. The browser sends 4 numbers to the server:
```
"I want to analyze the area between 
 longitude 81.25 to 81.35, latitude 21.20 to 21.30"
```

### Step 2: Get the Height Data 🏔️

The server has NASA satellite files that contain the height of every point on Earth (at 30m detail). It reads the relevant file and extracts a grid of heights for the rectangle.

**Analogy:** Imagine a chess board where each square has a number written on it — that number is the height of that spot. That's your elevation grid.

### Step 3: Fix the Data 🔧

The raw height data has "potholes" — random low points where water would get trapped. These are data errors, not real potholes. The system "fills" them so water can flow continuously downhill.

**Analogy:** Imagine pouring water on a bumpy surface. If there's a tiny dip, water gets stuck. The system smooths out these tiny dips so we can trace where water would REALLY flow.

### Step 4: Figure Out Which Way Water Flows 💧

For every point on the grid, look at the 8 surrounding points. Water flows toward the one that's most downhill. This is the **D8 algorithm**.

```
  NW  N  NE        32  64  128
   W  ●  E    →    16   ●    1
  SW  S  SE         8   4    2
```

Each direction gets a code number (1, 2, 4, 8, 16, 32, 64, 128). Every point stores one of these numbers, telling us "water at this point flows in THIS direction."

**Analogy:** Imagine placing a marble on each square of a tilted board. Which way does each marble roll? That's flow direction.

### Step 5: Count How Much Water Passes Through Each Point 🌊

Starting from hilltops (where only local rain falls), trace water downhill following the flow directions. Each point gets a count: how many upstream points send water through it.

- Hilltop: count = 1 (just its own rain)
- Small stream: count = 100 (100 points drain through it)
- River: count = 5000+ (huge upstream area)

Points with very high counts = rivers/streams. **We DON'T want to put a pond there** (it's already a river!).

### Step 6: Score Every Possible Pond Location 📊

For every point that's NOT a river, calculate a **suitability score (0 to 1)** based on 4 factors:

| Factor | Weight | Why |
|--------|--------|-----|
| **Elevation** (not too high, not too low) | 20% | Too low = river bed. Too high = hilltop with no water. Middle is best. |
| **Slope** (flatter is better) | 30% | Flat land is easier to dig, holds water better. |
| **Water flow** (more upstream water = better) | 30% | More water flowing toward this point = more water for the pond. |
| **Near a stream** (close but not ON it) | 20% | Near a stream catches water efficiently, but ON the stream = flooding risk. |

**The point with the highest score = best pond location!**

Then suppress a 225m radius around it and find the next best. Repeat for #3. → **Top 3 candidates**.

### Step 7: Trace the Catchment & Estimate Water Volume 🗺️

For each candidate, find the **pour point** (nearest stream cell) and trace upstream:

"Which points on the grid send their water to this pour point?"

This is done by a **Breadth-First Search (BFS)** — start at the pour point, check all 8 neighbors, if a neighbor's flow direction points toward us, it's in our catchment. Repeat outward until no more upstream cells found.

Then calculate:
```
Water per year = Catchment Area (m²) × 0.8m rainfall × 0.35 runoff coefficient
```

**Example:** 1,200,000 m² × 0.8 × 0.35 = **336,000 m³ of water per year**

---

## Part 4: How the Servers Work (Simple Version)

### The Setup

You have 4 lab computers (sys1, sys2, sys3, sys4). Think of them as 4 shops selling the same product.

```
        Customer (Browser)
              │
              ▼
     🚦 Traffic Light (Load Balancer)
        on sys1, port 5100
       /                \
      ▼                  ▼
  🏪 Shop 1          🏪 Shop 2
  (sys1:5000)        (sys2:5000)
      │
      ▼
  📦 Storage Locker (Redis Cache)
     on sys1
```

- **Traffic Light (Load Balancer):** Takes turns sending customers to Shop 1 and Shop 2
- **Storage Locker (Redis):** Remembers previous results. If someone asks the same question again, just give them the stored answer instantly (<50ms instead of 60+ seconds)
- **Each shop is identical** — same code, same data. If one shop closes (crashes), the traffic light sends everyone to the other shop

### Why Only 1 Customer at a Time Per Shop?

Each analysis uses ~300 MB of RAM. The shop only has 512 MB total. If two customers are served simultaneously: 300 + 300 = 600 MB > 512 MB → **CRASH** (Linux kills the process).

Solution: A **lock** (like a bathroom door lock) — only 1 analysis at a time. If a second request comes in, it gets: "Please wait, I'm busy" (HTTP 429 error).

### Why Use a Separate Thread?

The server has two jobs:
1. Heavy computation (60-120 seconds of terrain analysis)
2. Answering "are you alive?" health checks from the load balancer

If computation ran on the main thread, the server would FREEZE for 60+ seconds — the load balancer would think it's dead!

Solution: Heavy work runs on a **separate thread**. The main thread stays free to answer health checks.

---

## Part 5: The Frontend (What the User Sees)

### The Map
- **Leaflet** library shows an interactive map (like Google Maps but open-source)
- Base tiles from **OpenStreetMap** (free, no API key needed)
- User can zoom, pan, and draw a rectangle

### Drawing a Rectangle
- Click "Draw Rectangle" button → cursor changes to crosshair ✛
- Click and drag to draw a box on the map
- Minimum size enforced (~300m × 300m)
- The 4 corner coordinates are sent to the backend

### During Analysis (60-120 seconds)
- A progress bar shows estimated stages (loading data... computing flow... selecting candidates...)
- This is a **simulated** progress bar — the backend doesn't send real-time updates. The frontend just guesses where it should be based on typical timing.

### Results Display
- **3 colored markers** on the map: 🟢 #1 (best), 🟠 #2, 🟣 #3
- **Colored polygons** showing the catchment area for each candidate
- **Sidebar** with numbers: score, elevation, slope, catchment area, water volume
- Click a marker → popup with details

---

## Part 6: Viva Q&A — Simple Language Answers

### "What does your project do?"
> "It helps find the best location to build a rainwater harvesting pond. The user draws a rectangle on a map, the system analyzes the terrain using satellite elevation data, and recommends the top 3 spots where water naturally collects."

### "How does it find the best pond location?"
> "It uses the D8 algorithm — for every point on the grid, it figures out which way water would flow (toward the steepest downhill neighbor). Then it counts how much water passes through each point. Points with good water flow, flat terrain, moderate elevation, and near (but not on) a stream get the highest score."

### "What is D8?"
> "D8 stands for Deterministic 8-neighbor. Each point on the elevation grid has 8 neighbors. The algorithm calculates which neighbor has the steepest downhill slope, and assigns that as the flow direction. Water flows to that one neighbor. It's the most standard algorithm used in hydrology."

### "What is a catchment area?"
> "It's the entire region of land that drains water into a specific point. If you imagine pouring water anywhere inside the catchment, it would eventually flow to that point. We trace this by starting at the pond site and following flow directions backward — finding all points whose water flows toward us."

### "What is the formula for water volume?"
> "V = A × R × C. A is the catchment area in square meters. R is annual rainfall — we use 800mm or 0.8 meters, which is the average for Central India. C is 0.35, meaning 35% of rainfall becomes runoff. So for a 1.2 km² catchment: 1,200,000 × 0.8 × 0.35 = 336,000 cubic meters per year."

### "What is SRTM?"
> "It's data from a NASA shuttle mission that measured the height of every point on Earth using radar. We use the 30-meter resolution version — each data point covers a 30m × 30m area. The data comes as .hgt files, each covering a 1° × 1° area."

### "Why not use machine learning?"
> "Three reasons: First, there's no training data — nobody has a labeled dataset of 'good vs bad pond sites.' Second, village officials need to understand WHY a site was chosen — they can't trust a black box. Third, the physics of water flow is well-understood math — D8 flow direction has been used in hydrology for decades. ML would be overkill."

### "What CSD (Concurrent Systems Design) concepts did you use?"

> **Concurrency:** "The terrain analysis takes 60+ seconds and is CPU-heavy. If we ran it directly in the async event loop, the server would freeze. So we dispatch it to a thread pool using `asyncio.to_thread`. The event loop stays free to handle health checks."

> **Mutual exclusion:** "Each analysis uses ~300MB of RAM. Our servers have a 512MB limit. Two simultaneous analyses would crash the server. So we use a threading.Lock — only one analysis at a time. Extra requests get HTTP 429."

> **Caching:** "Redis stores results keyed by bounding box coordinates. Same query again? Instant response (<50ms) instead of recomputing (60+ seconds). Cache expires after 24 hours."

> **Load balancing:** "A Python load balancer distributes requests between sys1 and sys2 in round-robin. If one server dies, traffic automatically goes to the other."

> **Stateless design:** "Each server is independent — same code, same data, no shared state during computation. This makes horizontal scaling easy — just add another server."

### "What happens if Redis goes down?"
> "Nothing breaks. The code has try/except around every Redis call. If Redis is unreachable, it just skips the cache and computes the result normally. It's slower (60s vs 50ms) but the user still gets their answer."

### "What happens if a server crashes?"
> "The start_server.sh script has a while-true loop. If uvicorn dies, it restarts in 3 seconds. Meanwhile, the load balancer detects the dead server via health checks (every 10 seconds) and routes all traffic to the surviving server."

### "What libraries did you use and why?"
> "pysheds for hydrology (flow direction, accumulation — it's the standard Python hydrology library), NumPy for grid math, SciPy for interpolation and morphological operations, Shapely for polygon geometry, FastAPI for the web server, React + Leaflet for the frontend map, Redis for caching, httpx for the load balancer proxy."

### "Is there any AI/ML in this project?"
> "No neural networks or ML models. The 'AI' refers to automated multi-criteria decision analysis — a transparent, deterministic scoring system based on physical terrain properties. Every factor (elevation, slope, water flow, proximity to drainage) is explainable and physically meaningful."

### "What are the limitations?"
> 1. "30m SRTM resolution can't see features smaller than 30 meters"
> 2. "We use a fixed 800mm/year rainfall instead of live weather data"
> 3. "No land ownership data — the system doesn't know if the recommended site is on private land"
> 4. "One analysis at a time per server due to memory limits"
> 5. "No civil engineering design — just site selection, not pond blueprints"

---

## Part 7: The Report — Section by Section in Simple Words

Your submitted report has these sections. Here's what each says in plain English:

| Section | Plain English Summary |
|---------|---------------------|
| **Abstract** | "We built a web app that finds the best pond locations using satellite elevation data and water flow algorithms. It runs on 4 servers with a load balancer and cache." |
| **§1 Introduction** | "Villages need ponds. Finding where to dig is hard without experts. Our tool automates it using computers and satellite data." |
| **§2 Requirements** | "Here's what the system must do: show maps, analyze terrain, find catchment areas, estimate water volume. Here's where each feature lives in the code." |
| **§3 Architecture** | "4 lab computers, Python load balancer splits traffic, Redis caches results, SRTM files stored on each server." |
| **§4 Methodology** | "Step 1: Get height data. Step 2: Fix potholes in data. Step 3: Calculate which way water flows (D8). Step 4: Count water at each point. Step 5: Score locations. Step 6: Trace catchment. Step 7: Estimate water volume." |
| **§5 Implementation** | "API endpoints table, frontend is React+Leaflet, results cached in Redis." |
| **§6 CSD Themes** | "REST API design, thread pool concurrency, load balancing, Redis caching, error resilience, monolith choice, version control." |
| **§7 Results** | "For an 11km × 11km test area: catchment = 1.2 km², annual runoff = 336,000 m³, top score = 0.72." |
| **§8 Limitations** | "30m resolution is coarse, rainfall is hardcoded, no land ownership check, servers sometimes crash." |
| **§9 AI Usage** | "Used Gemini/AGY for design help, code generation, and debugging. All code reviewed and understood." |

### ⚠️ Things the Report Says That Are Slightly Different From Code

If the examiner checks code, know these:

| Report Says | Reality | What to Say |
|-------------|---------|-------------|
| React 18, TypeScript | Actually React 19, plain JavaScript | "We upgraded React and simplified to JSX during development" |
| Grid = 50×50 | Actually 30×30 | "Reduced to 30×30 to stay safe under the memory limit" |
| Response time 4-9 seconds | Actually 60-120 seconds | "4-9s was early testing on faster hardware. On the shared lab machines, it's longer." |
| Pysheds does catchment tracing | Actually our own BFS code | "Pysheds had bugs on repeated calls, so we wrote equivalent BFS in NumPy" |
| 3 scoring factors | Actually 4 (added elevation) | "Report summarized the top 3; code has a 4th factor for elevation preference" |

---

## Part 8: Quick-Fire Flashcards

Read these right before the viva. Each is one question + one-sentence answer.

1. **What is SRTM?** → NASA satellite height data, 30m resolution, free to download
2. **What is D8?** → Each cell flows to steepest of 8 neighbors
3. **What is flow accumulation?** → Count of upstream cells draining through a point
4. **What is a catchment?** → All land whose water flows to a specific point
5. **What is a pour point?** → The drainage outlet where catchment water exits
6. **What is Redis used for?** → Caching results so repeated queries are instant
7. **What is the load balancer?** → Distributes requests between sys1 and sys2
8. **Why thread pool?** → Heavy computation would freeze the server otherwise
9. **Why mutex lock?** → Prevent 2 analyses running simultaneously (would exceed 512MB RAM)
10. **What is the water formula?** → V = Area × Rainfall × Runoff Coefficient
11. **What are the scoring weights?** → Elevation 20%, Slope 30%, Accumulation 30%, Proximity 20%
12. **Why no ML?** → No training data, need explainability, physics works fine
13. **What if Redis dies?** → System still works, just slower (computes instead of cache)
14. **What if a server crashes?** → Auto-restart in 3s, LB routes to surviving server
15. **What is BFS?** → Breadth-First Search — explore neighbors level by level (used for catchment tracing)
16. **What is pysheds?** → Python hydrology library for pit filling, flow direction, accumulation
17. **What is GeoJSON?** → Standard format for geographic shapes as JSON
18. **What is Leaflet?** → JavaScript map library (like Google Maps but free/open-source)
19. **What is FastAPI?** → Python web framework for building REST APIs
20. **What is a distributed monolith?** → Same full app deployed on multiple machines with an LB in front

---

*You got this! The concepts are simpler than they sound. 💪*
