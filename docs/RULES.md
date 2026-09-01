# Engineering Rules

## AI-based Village Pond Planning System

**Version:** 1.0  
**Date:** 2026-08-10  
**Status:** Active

---

## Technology Stack Rules

1. **Do not change the core technology stack** (React/Vite/TypeScript frontend, FastAPI/Python backend, MongoDB) without explicit approval.
2. **Do not silently replace libraries.** If a library must be swapped, document the reason in DECISIONS.md and obtain approval.
3. **Do not silently replace APIs.** All external API changes must be documented.
4. **Do not introduce unnecessary frameworks.** Every dependency must have a clear technical justification.
5. **Use Tailwind CSS for styling** as specified in the stack. Do not introduce additional CSS frameworks.

---

## Data & API Rules

6. **Do not create fake external API responses.** All data must come from real APIs or be clearly labeled as sample/demo data.
7. **Do not hardcode production-like data** unless explicitly identified as sample/demo data with clear comments.
8. **Validate external API responses.** Never blindly trust external data.
9. **Handle API failures gracefully.** Timeouts, invalid responses, and unavailable APIs must produce clear error messages, not silent failures.
10. **Cache external API responses** where appropriate to reduce API calls and improve reliability.

---

## Architecture Rules

11. **Keep backend, frontend, and geospatial logic separated.** Do not mix concerns.
12. **Maintain the monolithic architecture.** Do not introduce microservices without explicit approval.
13. **Every major architectural change must be recorded in DECISIONS.md.**
14. **If a requested implementation conflicts with an existing architectural decision, STOP and explain the conflict** instead of silently changing architecture.
15. **Preserve backward compatibility where practical.** Do not break working APIs without migration.

---

## Code Quality Rules

16. **Do not delete working functionality to solve an unrelated issue.**
17. **All algorithms must be documented** with input, output, assumptions, and limitations.
18. **Use Pydantic schemas** for all API request/response validation.
19. **Use environment variables** for API keys, database URIs, and configuration.
20. **Never expose secrets in source code.** Use `.env` files excluded from Git.
21. **Apply proper input validation** on all user-facing endpoints.
22. **Keep CORS configured deliberately.** Do not use wildcard `*` in production.

---

## Development Process Rules

23. **Work phase-by-phase.** Do not start the next phase until the current phase satisfies acceptance criteria.
24. **Before beginning any phase, read:** PRD.md, ARCHITECTURE.md, RULES.md, PHASES.md, DECISIONS.md, MEMORY.md.
25. **After completing any phase, update:** MEMORY.md, LEARN.md, and relevant documentation.
26. **Do not silently change algorithms.** Any algorithm change must be documented.
27. **Test every phase** before marking it complete.

---

## Academic Integrity Rules

28. **The student must understand every component.** Do not dump large unexplained blocks of code.
29. **Explain every significant algorithm** with input, output, intuition, steps, and limitations.
30. **Cite AI tool usage** in any reports or documentation.
31. **Never fabricate research claims, API capabilities, accuracy, or real-world engineering guarantees.**
32. **All estimates must be clearly labeled as estimates**, not guaranteed engineering outputs.

---

## Geospatial / Domain Rules

33. **Satellite imagery does not establish legal land ownership.** Always label land availability data as input/reference data.
34. **Do not use vague "AI" terminology** where a deterministic geospatial/hydrological algorithm is more appropriate.
35. **Do not introduce ML models** unless they provide clear value over transparent deterministic methods.
36. **Store large raster/DEM files on the filesystem,** not in MongoDB. Use MongoDB for metadata and results.
37. **Handle NoData values in DEM data** explicitly — never treat them as valid elevation.

---

## Security Rules

38. **No secrets committed to Git.** Use `.gitignore` for `.env` files.
39. **Validate file uploads** (size, type, content).
40. **Return reasonable API error messages** — do not expose internal stack traces to users.
41. **Sanitize user inputs** before using in file paths or database queries.

---

## Change Control

42. If a better technical approach is discovered during implementation:
    - DO NOT silently switch.
    - Document: Current Decision → Problem → Proposed Change → Why It's Better → Files Affected → Migration Cost → Impact on Future Phases.
    - Wait for approval if the change affects a LOCKED decision.
43. Minor implementation details may be improved without approval if they do not alter the architecture.

---

## Phase 2 — Contour Input Rules (Added 2026-08-29)

44. **No sample-specific hardcoding.** Never hardcode coordinates, elevation values, polygon shapes, or catchment areas from the sample KML/KMZ. All results must be derived from the uploaded input.
45. **No filename-specific logic.** Do not branch based on the filename of the uploaded contour map. Every valid KML/KMZ must be processed identically.
46. **Do not assume visual features are explicitly encoded.** A river or drainage visible on a rendered map may not exist as a named KML feature. Always inspect actual KML geometry, folder names, and styles before classifying features.
47. **Pond candidates must not overlap water/drainage exclusion zones.** Whether the exclusion zone comes from explicit KML water features (Case A) or terrain-derived drainage (Case B), candidates must be excluded from that zone plus a configurable buffer.
48. **API routes must orchestrate, not process.** The FastAPI route handler for contour analysis must only validate, call service, and format response. All geospatial logic lives in `geo/` modules.
49. **Terrain-derived drainage is not verified river data.** Any drainage network computed from flow accumulation must be labelled in the API response as "terrain-derived" and explicitly noted as not verified geographic or legal river location data.
50. **KML/KMZ parsing must remain separate from the hydrology engine.** The `kml_parser.py` module produces normalized contour geometry. The hydrology modules consume a generic elevation grid, not KML directly. This separation enables future DEM input to reuse the same downstream pipeline.

