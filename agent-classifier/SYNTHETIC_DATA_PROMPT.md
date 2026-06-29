# LLM Prompt: Generate Synthetic Training Data for Agent Routing Classifier

> **Instructions**: Copy this entire prompt and give it to any LLM (GPT-4, Claude, Gemini, etc.) to generate synthetic training data. Run it multiple times with different agent batches (the prompt tells the LLM which agents to generate for in each run). Target: **1800-2000 rows per agent, 10 agents = ~18,000-20,000 total rows**.

---

## THE PROMPT (copy everything below this line)

---

You are a synthetic dataset generator for a fleet management AI chatboard. I need you to generate realistic user queries that a fleet manager, dispatcher, operations head, or logistics analyst would type into a chatbox. Each query must be labeled with exactly ONE agent class.

### SYSTEM CONTEXT

This is **Smart-Truck**, an Indian trucking/logistics fleet management platform with:
- **Database**: 7.4 million trip records, ~780K drivers, ~342K vehicles, ~21K locations, ~5K customers
- **Backend API**: Dashboard, drivers, trips, vehicles, routes, locations endpoints
- **ML Service**: 9 trained models — ETA prediction (XGBoost+LightGBM), SLA prediction (XGBoost classifier), anomaly detection (Isolation Forest), driver scoring (hybrid weighted), demand forecasting (Ridge+ExpSmoothing), route optimization (Dijkstra graph), driver recommendation (route-experience ranking), fatigue prediction, client demand forecasting
- **Domain**: Indian trucking — routes between Indian cities, Hindi/English mixed queries common, driver names are Indian, vehicle IDs look like "CG04MC9150", "MH12AB1234"

### THE 10 AGENT CLASSES

```
AGENT 0: fleet_overview
AGENT 1: driver_performance
AGENT 2: trip_management
AGENT 3: route_intelligence
AGENT 4: vehicle_tracking
AGENT 5: eta_sla_prediction
AGENT 6: anomaly_alert
AGENT 7: demand_forecasting
AGENT 8: route_optimization
AGENT 9: driver_safety
```

### DETAILED AGENT DEFINITIONS (read carefully — this defines the classification boundary)

---

**AGENT 0: fleet_overview**
Handles: Fleet-wide KPIs, dashboard summaries, daily/weekly/monthly trends, overall fleet health, top-N rankings across the entire fleet, route heatmaps, fleet comparison over time.

API tools available:
- `GET /dashboard/summary` → total_trips, total_drivers, total_vehicles, total_distance_km, avg_speed_kmph, eta_success_rate
- `GET /dashboard/daily-trend?days=N` → daily stats: total_trips, total_distance_km, avg_speed, eta_success_rate, active_drivers, active_vehicles
- `GET /dashboard/top-drivers?limit=N` → top drivers by trip count with eta_success_rate, avg_speed_kmph
- `GET /dashboard/route-heatmap?limit=N` → most traveled routes with trip_count, avg_duration, eta_success_rate
- `GET /dashboard/alerts/recent?limit=N` → recent system alerts

Example queries that belong here:
- "How many trips happened this month?"
- "Show me fleet summary"
- "What's our overall ETA success rate?"
- "Daily trend for last 2 weeks"
- "Who are the top 10 drivers?"
- "Which routes are busiest?"
- "How many active vehicles do we have?"
- "Fleet performance last 30 days"

What does NOT belong here:
- Asking about a SPECIFIC driver → agent 1
- Asking about a SPECIFIC trip → agent 2
- Asking about a SPECIFIC route's performance → agent 3
- Prediction requests → agents 5/7/8

---

**AGENT 1: driver_performance**
Handles: Individual driver profiles, driver performance scores, driver rankings by score, driver trends over time, driving behavior patterns (speed distribution, hourly patterns, day-of-week patterns), driver comparisons, composite score breakdowns.

API tools available:
- `GET /drivers?search=&sort_by=&page=` → list/search drivers with composite_score
- `GET /drivers/{id}` → driver detail: summary stats, recent trips, vehicles used, frequent routes
- `GET /drivers/{id}/trips` → driver trip history
- `GET /drivers/{id}/trend?group_by=month` → performance trend: trip_count, avg_duration, eta_success_rate, avg_speed over time
- `GET /drivers/{id}/driving-pattern` → hourly patterns, speed distribution, daily patterns
- `GET /ml/drivers/scores?limit=N` → all driver scores with composite_score, risk_level
- `GET /ml/drivers/{id}/score` → individual score breakdown: eta_score, speed_score, consistency_score, experience_score, efficiency_score

Example queries:
- "Show me Rajesh Kumar's performance"
- "What is driver 4521's score?"
- "Compare top 5 drivers by consistency"
- "Driver trend for Amit Singh last 6 months"
- "Which drivers have score below 50?"
- "Show driving pattern for driver 782"
- "List all high-risk drivers"
- "How many trips has Suresh Yadav completed?"

What does NOT belong here:
- Fleet-wide stats without mentioning a driver → agent 0
- "Predict if driver X will be on time" → agent 5
- "Is driver X fatigued?" → agent 9
- "Recommend a driver for route X→Y" → agent 8

---

**AGENT 2: trip_management**
Handles: Trip search/lookup, trip filtering (by driver, vehicle, route, status, date range), trip details (with waypoints, comparisons), trip statistics, trip history queries, specific trip investigation.

API tools available:
- `GET /trips?driver_id=&vehicle_id=&origin=&destination=&trip_status=&eta_met=&date_from=&date_to=` → filtered trip list
- `GET /trips/stats` → total_trips, completed_trips, active_trips, avg_duration, avg_speed, eta_success_rate
- `GET /trips/{id}` → trip detail: full trip info, waypoints, driver stats, route stats, vehicle stats, route comparison
- `GET /locations/route-stats?origin=&destination=` → quick route stats with OSRM fallback

Example queries:
- "Show me trip 45892"
- "List all trips from Raipur to Nagpur last week"
- "How many active trips right now?"
- "Find completed trips for driver 321 in March"
- "Trip details for dispatch entry DIS-2026-78432"
- "Show trips with ETA missed between Jan 1 and Jan 15"
- "What was the duration of trip 9923?"
- "List all trips for vehicle CG04MC9150"
- "Trips from Mumbai to Delhi this month"

What does NOT belong here:
- "How long will the next trip take?" → agent 5
- "Are there anomalies in recent trips?" → agent 6
- Overall trip statistics for fleet → agent 0

---

**AGENT 3: route_intelligence**
Handles: Route-specific performance analysis, route comparison, time-of-day patterns for routes, day-of-week patterns, route duration analysis, route ETA success rates, top drivers on a specific route, recent trip history on a route.

API tools available:
- `GET /routes?search=&sort_by=` → list routes with trip_count, avg_duration_min, eta_success_rate, avg_distance_km
- `GET /routes/detail?origin=&destination=` → route detail: summary, time_patterns (hour and day-of-week), top_drivers on route, recent_trips

Example queries:
- "Performance of Raipur to Nagpur route"
- "Which route has the worst ETA success rate?"
- "Time pattern analysis for Delhi to Jaipur"
- "Best time of day to dispatch on Mumbai-Pune route"
- "Compare Raipur-Nagpur vs Raipur-Kolkata routes"
- "Top drivers on the Hyderabad to Bangalore route"
- "Average duration on Chennai to Coimbatore route"
- "Show route performance sorted by ETA success"
- "Which day of week is best for Lucknow to Kanpur route?"

What does NOT belong here:
- "Find the optimal route" → agent 8
- "Predict trip time on this route" → agent 5
- "How many trips on this route next week?" → agent 7
- Searching for specific trips on a route → agent 2

---

**AGENT 4: vehicle_tracking**
Handles: Vehicle details, vehicle utilization, vehicle trip history, drivers who used a vehicle, vehicle performance metrics, vehicle fleet listing, vehicle search.

API tools available:
- `GET /vehicles?search=&sort_by=` → list vehicles with total_trips, avg_speed, total_distance, eta_success_rate
- `GET /vehicles/{id}` → vehicle detail: summary, drivers_used, recent_trips, vehicle_routes, route_benchmarks, monthly_trend
- `GET /vehicles/{id}/trips` → vehicle trip history

Example queries:
- "Show details for vehicle CG04MC9150"
- "Which vehicles have the highest mileage?"
- "List all trips for vehicle MH12AB1234"
- "How many drivers used vehicle 567?"
- "Vehicle utilization report"
- "Monthly trend for vehicle CG04MC9150"
- "Which vehicles are underperforming?"
- "Show vehicle fleet sorted by total trips"
- "What routes does vehicle RJ14CD5678 usually cover?"

What does NOT belong here:
- "Which vehicle should I assign?" → agent 8
- Trip details (even if vehicle is mentioned, if focus is the trip) → agent 2

---

**AGENT 5: eta_sla_prediction**
Handles: Predicting estimated arrival time for a planned/upcoming trip, predicting on-time probability (SLA), delay risk assessment, "will this trip be on time?" type questions.

ML tools available:
- `POST /ml/predict/eta` → input: origin, destination, driver_id, vehicle_id, trip_km, trip_start → output: predicted_duration_minutes, features_used, route_avg, driver_avg
- `POST /ml/predict/sla` → input: same as ETA → output: on_time_probability, prediction (yes/no), risk_level, contributing_factors

Example queries:
- "Predict ETA for a trip from Raipur to Nagpur"
- "How long will it take from Delhi to Jaipur with driver 4521?"
- "What's the on-time probability for Mumbai to Pune tomorrow morning?"
- "Will driver Rajesh Kumar deliver on time from Kolkata to Bhubaneswar?"
- "SLA prediction for trip starting at 6 AM from Hyderabad to Bangalore"
- "Estimate delivery time if we dispatch vehicle CG04MC9150 from Chennai to Coimbatore"
- "Risk of delay for Lucknow to Kanpur route at 3 PM?"
- "Predict trip duration for 450 km journey from Indore to Bhopal"

What does NOT belong here:
- Past trip analysis → agent 2
- Route average duration (historical stat, not prediction) → agent 3
- "How long did trip X take?" → agent 2

---

**AGENT 6: anomaly_alert**
Handles: Scanning trips for anomalies, detecting unusual trip patterns, managing alerts, investigating flagged trips, severity analysis of detected issues, "something wrong" type queries.

ML tools available:
- `POST /ml/scan/anomalies?days=N` → batch scan: trips_scanned, anomalies_found, alerts_created, severity_breakdown, top_anomalies
- `GET /dashboard/alerts/recent?limit=N` → recent alerts with type, severity, title, message

Example queries:
- "Scan last 7 days for anomalies"
- "Are there any unusual trips this week?"
- "Show recent alerts"
- "How many high-severity anomalies were detected?"
- "Scan for anomalies in trips from Raipur"
- "Any suspicious trip patterns last month?"
- "Show critical alerts"
- "Check if there are any outlier trips today"
- "What anomalies were found in the last scan?"
- "Run anomaly detection on last 30 days"
- "Any trips that took unusually long?"

What does NOT belong here:
- "Predict if this trip will be delayed" → agent 5
- "Show driver's risk level" → agent 1 or 9
- General fleet stats → agent 0

---

**AGENT 7: demand_forecasting**
Handles: Predicting future trip demand (how many trips will happen), route-level demand forecast, client/customer demand forecast, weekly volume predictions, growth rate analysis, seasonal patterns.

ML tools available:
- `GET /ml/forecast/demand?route=origin->destination` → per-route 7-day forecast: historical_avg, trend (up/down/stable), daily predictions
- `GET /ml/forecast/demand` → fleet-wide demand forecast across top 50 routes
- `GET /ml/forecast/trips?route=optional` → trip volume forecast
- `GET /ml/clients/forecast?client=name` → client-level demand forecast with growth_rate, seasonal_pattern
- `GET /ml/clients` → client list
- `GET /ml/clients/{name}/profile` → client profile: total_trips, avg_trips_per_week, top_routes, day_of_week_pattern, monthly_trend

Example queries:
- "How many trips expected next week on Delhi to Jaipur?"
- "Demand forecast for Mumbai-Pune route"
- "Fleet-wide trip prediction for next 7 days"
- "Is demand growing or declining on Raipur-Nagpur?"
- "Client forecast for Tata Steel"
- "How many trips will ABC Logistics need next week?"
- "Show demand trend for top 10 routes"
- "Seasonal pattern for Hyderabad to Bangalore demand"
- "Predict next week trip volume"
- "Which routes will be busiest next week?"
- "Client profile for Reliance Industries"

What does NOT belong here:
- "Predict duration of a trip" → agent 5
- Historical trip counts → agent 0 or 2
- Route performance (not volume) → agent 3

---

**AGENT 8: route_optimization**
Handles: Finding the best/optimal route between locations, multi-stop route planning, hub/warehouse analysis, recommending the best driver for a specific route, driver-route matching.

ML tools available:
- `POST /ml/optimize/route` → input: origin, destination, hour, day_of_week → output: recommended path (with intermediate stops), alternatives, segment details, direct_stats
- `GET /ml/optimize/hubs` → hub locations by frequency analysis
- `POST /ml/recommend/drivers` → input: origin, destination, top_n → output: experienced_on_route drivers, similar_route_experience drivers with scores

Example queries:
- "Best route from Raipur to Mumbai"
- "Optimize route from Delhi to Chennai"
- "Which driver should I assign for Kolkata to Bhubaneswar?"
- "Recommend top 5 drivers for Nagpur to Hyderabad route"
- "Find alternative routes from Jaipur to Ahmedabad"
- "What are the major hub locations?"
- "Suggest the fastest route from Lucknow to Patna"
- "Who is the best driver for the Mumbai-Pune route?"
- "Multi-stop route from Raipur to Nagpur via Durg"
- "Which drivers have experience on Delhi-Jaipur route?"

What does NOT belong here:
- Route historical performance → agent 3
- "How long will this route take?" → agent 5
- Driver score/ranking in general → agent 1

---

**AGENT 9: driver_safety**
Handles: Driver fatigue risk assessment, workload monitoring, rest compliance, safety alerts, driving hour analysis, night trip monitoring, consecutive driving days, fatigue risk fleet-wide view.

ML tools available:
- `GET /ml/drivers/fatigue` → fleet-wide fatigue: summary (critical/high/medium/low counts), top_at_risk drivers
- `GET /ml/drivers/{id}/fatigue` → individual: fatigue_risk, fatigue_probability, fatigue_score, contributing_factors (trips_last_24h, hours_driving_last_24h, night_trips_last_7d, consecutive_days_active, recent_delay_rate, speed_variance)

Example queries:
- "Check fatigue risk for driver Rajesh Kumar"
- "Which drivers are at critical fatigue risk?"
- "Show fleet-wide fatigue summary"
- "How many hours has driver 4521 driven in last 24 hours?"
- "Night trip count for driver Amit Singh this week"
- "Is driver 782 safe to dispatch right now?"
- "Drivers who worked more than 5 consecutive days"
- "Show top 10 most fatigued drivers"
- "Rest compliance check for all drivers"
- "Safety dashboard"
- "Who should not be driving today?"
- "Driver workload analysis"

What does NOT belong here:
- Driver performance score → agent 1
- Trip-specific safety (anomaly) → agent 6
- General driver details → agent 1

---

### ENTITY EXAMPLES TO USE IN QUERIES

Use these real-world examples to make queries realistic. Mix and match freely.

**Indian Driver Names** (use these and invent similar ones):
Rajesh Kumar, Amit Singh, Suresh Yadav, Ramesh Sharma, Vikram Patel, Manoj Verma, Anil Tiwari, Deepak Gupta, Sanjay Mishra, Ravi Chauhan, Prakash Nair, Ganesh Reddy, Mohan Das, Kishore Pandey, Bijoy Roy, Ashok Mehra, Naveen Joshi, Dinesh Rawat, Santosh Patil, Mukesh Agarwal, Harish Dubey, Gopal Krishna, Balram Pal, Jagdish Thakur, Vinod Saxena, Pappu Singh, Chhotu Ram, Bablu Prasad, Phool Chand, Kallu Bhai

**Vehicle IDs** (Indian format — state code + district + series + number):
CG04MC9150, MH12AB1234, RJ14CD5678, DL01EF9012, GJ05GH3456, UP32JK7890, MP09LM2345, TN07NP6789, KA01QR0123, AP28ST4567, HR26UV8901, PB10WX2345, WB04YZ6789, OR05AA1234, JH01BB5678, CH01CC9012, UK07DD3456, HP01EE7890

**Indian Locations/Cities** (origins and destinations):
Raipur, Nagpur, Mumbai, Delhi, Jaipur, Ahmedabad, Pune, Hyderabad, Bangalore, Chennai, Kolkata, Bhubaneswar, Lucknow, Kanpur, Patna, Indore, Bhopal, Coimbatore, Durg, Bhilai, Bilaspur, Korba, Rajnandgaon, Ambikapur, Jagdalpur, Surat, Vadodara, Vizag, Vijaywada, Guwahati, Ranchi, Jamshedpur, Dhanbad, Varanasi, Allahabad, Agra, Gwalior, Jabalpur, Rewa, Satna, Siliguri, Mangalore, Mysore, Kochi, Thiruvananthapuram, Madurai, Tiruchirappalli, Salem, Nashik, Aurangabad, Solapur, Kolhapur, Hubli

**Customer/Client Names** (Indian companies):
Tata Steel, Reliance Industries, Ambuja Cement, UltraTech Cement, ACC Limited, JSW Steel, Hindalco, Vedanta Resources, Dalmia Bharat, Shree Cement, Grasim Industries, Larsen Toubro, Adani Group, Mahindra Logistics, Jindal Steel, SAIL, NALCO, NMDC, Coal India, NTPC, BHEL, GAIL, Indian Oil, BPCL, HPCL

**Date References** (use both absolute and relative):
- Absolute: "January 2026", "15th March", "2026-03-01 to 2026-03-15", "last quarter"
- Relative: "today", "yesterday", "last week", "this month", "past 7 days", "last 30 days", "this quarter"

**Trip IDs**: Use numbers like 45892, 9923, 102344, 78432, 55001, etc.
**Driver IDs**: Use numbers like 4521, 782, 321, 1056, 2890, 15432, etc.

---

### QUERY VARIATION REQUIREMENTS

For EACH agent, generate queries with these variation dimensions:

1. **Formality levels**:
   - Formal: "Could you provide the fleet performance summary for last week?"
   - Casual: "show me fleet stats last week"
   - Hinglish: "fleet ka overall performance dikhao last week ka"
   - Shorthand: "fleet perf last wk"

2. **Specificity levels**:
   - Vague: "how are things going?"
   - Moderate: "how is fleet performing?"
   - Specific: "what is the ETA success rate for last 30 days?"
   - Hyper-specific: "show daily ETA success rate trend from March 1 to March 15 2026"

3. **Intent expressions**:
   - Direct question: "What is the average speed of fleet?"
   - Command: "Show fleet summary"
   - Implicit: "I need to prepare a report on fleet performance"
   - Conversational: "hey, just checking on how the fleet did today"

4. **Entity mention patterns**:
   - By name: "Rajesh Kumar's performance"
   - By ID: "driver 4521 performance"
   - By description: "that driver who does the Raipur-Nagpur route"
   - No entity: "show top performing drivers"

5. **Temporal expressions**:
   - No time: "fleet summary"
   - Relative: "last week's performance"
   - Absolute: "performance from Jan 1 to Jan 31 2026"
   - Vague: "recently"

6. **Complex/compound queries** (still single-agent — the DOMINANT intent determines the label):
   - "Show me driver Rajesh Kumar's score and his trip count" → agent 1 (driver_performance)
   - "I want to plan a trip from Raipur to Nagpur, what's the best route and predicted time?" → agent 8 (route_optimization, since PLANNING is the primary intent)

7. **Edge cases / boundary queries** (include ~100 per agent):
   - Queries that SEEM like they could go to another agent but shouldn't
   - Example: "How many trips did driver 4521 complete?" → agent 1 (NOT agent 2, because the focus is driver performance)
   - Example: "Show all trips on the Mumbai-Pune route" → agent 2 (NOT agent 3, because the focus is listing trips)
   - Example: "Fleet fatigue summary" → agent 9 (NOT agent 0, because fatigue is safety-specific)

8. **Typos and misspellings** (~5% of queries):
   - "shwo me flee sumary"
   - "drivr perfomance for rajesh"
   - "eta predicton mumbai to pune"

9. **Domain jargon**:
   - "challan status for trip 45892"
   - "dispatch readiness check"
   - "consignment tracking"
   - "loading/unloading time"
   - "transporter report"

---

### OUTPUT FORMAT

Generate a CSV with exactly 2 columns:

```
query,agent
"show me fleet summary",fleet_overview
"Rajesh Kumar's performance score",driver_performance
"predict ETA from Raipur to Nagpur",eta_sla_prediction
```

Rules:
- Double-quote every query value
- Agent labels must be exactly one of: `fleet_overview`, `driver_performance`, `trip_management`, `route_intelligence`, `vehicle_tracking`, `eta_sla_prediction`, `anomaly_alert`, `demand_forecasting`, `route_optimization`, `driver_safety`
- No header row duplication
- No empty rows
- No additional columns

---

### GENERATION INSTRUCTIONS

Generate **2000 rows** for each of the following agents in this batch:

**BATCH 1** (run this prompt first):
- `fleet_overview` (2000 rows)
- `driver_performance` (2000 rows)

**BATCH 2** (run this prompt with this section changed):
- `trip_management` (2000 rows)
- `route_intelligence` (2000 rows)

**BATCH 3**:
- `vehicle_tracking` (2000 rows)
- `eta_sla_prediction` (2000 rows)

**BATCH 4**:
- `anomaly_alert` (2000 rows)
- `demand_forecasting` (2000 rows)

**BATCH 5**:
- `route_optimization` (2000 rows)
- `driver_safety` (2000 rows)

For the current run, generate **BATCH [INSERT BATCH NUMBER HERE]**.

Ensure:
- At least 30% of queries mention specific entities (driver names, vehicle IDs, locations, dates)
- At least 5% contain Hinglish (Hindi-English mix)
- At least 5% contain typos/misspellings
- At least 10% are boundary/edge-case queries
- At least 15% use casual/shorthand language
- No two queries are identical
- Distribution across all variation dimensions is roughly uniform

Start generating the CSV now. Output ONLY the CSV, no explanations.
