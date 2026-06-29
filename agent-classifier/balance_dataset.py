"""
Balance the agent classifier dataset.
Reads dataset.txt, cleans it, generates synthetic rows via templates + augmentation,
outputs a balanced dataset.csv with ~1500 rows per class.
"""
import csv
import random
import re
import io

random.seed(42)
TARGET_PER_CLASS = 1500

# ── Entity pools ──────────────────────────────────────────────────────────────

DRIVERS = [
    "Rajesh Kumar", "Amit Singh", "Suresh Yadav", "Ramesh Sharma", "Vikram Patel",
    "Manoj Verma", "Anil Tiwari", "Deepak Gupta", "Sanjay Mishra", "Ravi Chauhan",
    "Prakash Nair", "Ganesh Reddy", "Mohan Das", "Kishore Pandey", "Bijoy Roy",
    "Ashok Mehra", "Naveen Joshi", "Dinesh Rawat", "Santosh Patil", "Mukesh Agarwal",
    "Harish Dubey", "Gopal Krishna", "Balram Pal", "Jagdish Thakur", "Vinod Saxena",
    "Pappu Singh", "Chhotu Ram", "Bablu Prasad", "Phool Chand", "Kallu Bhai",
    "Rakesh Tomar", "Bhupendra Rana", "Mahesh Jat", "Omprakash Meena", "Laxman Sahu",
    "Tulsi Ram", "Shyam Sundar", "Brajesh Pal", "Kailash Chandra", "Devendra Nath",
]

DRIVER_IDS = list(range(100, 20000, 137))[:60]

VEHICLES = [
    "CG04MC9150", "MH12AB1234", "RJ14CD5678", "DL01EF9012", "GJ05GH3456",
    "UP32JK7890", "MP09LM2345", "TN07NP6789", "KA01QR0123", "AP28ST4567",
    "HR26UV8901", "PB10WX2345", "WB04YZ6789", "OR05AA1234", "JH01BB5678",
    "CH01CC9012", "UK07DD3456", "HP01EE7890", "CG07KF4521", "MH04PQ8834",
    "RJ19RS2201", "DL08TU3309", "GJ12VW5567", "UP16XY7743", "MP20ZA9981",
]

CITIES = [
    "Raipur", "Nagpur", "Mumbai", "Delhi", "Jaipur", "Ahmedabad", "Pune",
    "Hyderabad", "Bangalore", "Chennai", "Kolkata", "Bhubaneswar", "Lucknow",
    "Kanpur", "Patna", "Indore", "Bhopal", "Coimbatore", "Durg", "Bhilai",
    "Bilaspur", "Korba", "Rajnandgaon", "Surat", "Vadodara", "Vizag",
    "Vijaywada", "Ranchi", "Jamshedpur", "Varanasi", "Agra", "Gwalior",
    "Jabalpur", "Nashik", "Aurangabad", "Kolhapur", "Hubli", "Mysore",
    "Kochi", "Madurai", "Salem", "Mangalore", "Siliguri", "Dhanbad",
    "Rewa", "Satna", "Allahabad", "Thiruvananthapuram", "Solapur", "Tiruchirappalli",
]

CLIENTS = [
    "Tata Steel", "Reliance Industries", "Ambuja Cement", "UltraTech Cement",
    "ACC Limited", "JSW Steel", "Hindalco", "Vedanta Resources", "Dalmia Bharat",
    "Shree Cement", "Grasim Industries", "Larsen Toubro", "Adani Group",
    "Mahindra Logistics", "Jindal Steel", "SAIL", "NALCO", "NMDC",
    "Coal India", "NTPC", "BHEL", "GAIL", "Indian Oil", "BPCL", "HPCL",
    "Ultratech", "JK Cement", "Birla Corp", "Orient Cement", "Ramco Cement",
]

DATE_EXPRS = [
    "today", "yesterday", "last week", "this week", "last month", "this month",
    "past 7 days", "last 30 days", "past 2 weeks", "last 14 days", "this quarter",
    "last quarter", "past 3 days", "last 3 months", "January 2026", "February 2026",
    "March 2026", "2026-01-01 to 2026-01-15", "2026-02-01 to 2026-02-28",
    "2026-03-01 to 2026-03-15", "last 60 days", "past 90 days", "recently",
    "kal", "aaj", "is hafte", "pichle mahine", "is mahine",
]

TRIP_IDS = list(range(10001, 99999, 73))[:80]
NUMBERS = [3, 5, 7, 10, 15, 20, 25, 50, 100]
HOURS = ["5 AM", "6 AM", "7 AM", "8 AM", "9 AM", "10 AM", "11 AM",
         "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "8 PM", "10 PM", "11 PM"]
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DISTANCES = ["100 km", "150 km", "200 km", "300 km", "450 km", "500 km", "600 km", "800 km"]


def r_driver():
    return random.choice(DRIVERS)

def r_did():
    return str(random.choice(DRIVER_IDS))

def r_vehicle():
    return random.choice(VEHICLES)

def r_origin():
    return random.choice(CITIES)

def r_dest(exclude=None):
    c = [x for x in CITIES if x != exclude]
    return random.choice(c)

def r_date():
    return random.choice(DATE_EXPRS)

def r_num():
    return str(random.choice(NUMBERS))

def r_client():
    return random.choice(CLIENTS)

def r_trip():
    return str(random.choice(TRIP_IDS))

def r_hour():
    return random.choice(HOURS)

def r_day():
    return random.choice(DAYS_OF_WEEK)

def r_dist():
    return random.choice(DISTANCES)

def route_pair():
    o = r_origin()
    d = r_dest(o)
    return o, d


def fill(template):
    """Fill a template with random entities. Supports {driver}, {did}, {vehicle}, etc."""
    o, d = route_pair()
    replacements = {
        "{driver}": r_driver(),
        "{did}": r_did(),
        "{vehicle}": r_vehicle(),
        "{origin}": o,
        "{dest}": d,
        "{date}": r_date(),
        "{num}": r_num(),
        "{client}": r_client(),
        "{trip}": r_trip(),
        "{hour}": r_hour(),
        "{day}": r_day(),
        "{dist}": r_dist(),
        "{route}": f"{o} to {d}",
    }
    result = template
    for key, val in replacements.items():
        result = result.replace(key, val)
    return result


# ── Templates per agent ───────────────────────────────────────────────────────

TEMPLATES = {}

TEMPLATES["fleet_overview"] = [
    "show me fleet summary",
    "fleet performance for {date}",
    "how many trips happened {date}",
    "total trips {date}",
    "daily trend for {date}",
    "how many active drivers {date}",
    "fleet health overview",
    "top {num} drivers across fleet",
    "which routes are busiest {date}",
    "overall ETA success rate",
    "show dashboard summary",
    "fleet stats for {date}",
    "how is fleet performing {date}",
    "fleet ka overall performance {date}",
    "fleet perf {date}",
    "compare fleet performance {date}",
    "avg speed across fleet",
    "distance covered by fleet {date}",
    "show fleet trend {date}",
    "how many active vehicles {date}",
    "route heatmap",
    "fleet KPI dashboard",
    "fleet summary with alerts",
    "recent alerts",
    "fleet growth trend {date}",
    "total vehicles and drivers count",
    "how many trips completed {date}",
    "fleet overview report",
    "weekly fleet performance summary",
    "fleet utilization overview",
    "which day had highest trips {date}",
    "trend of ETA success rate {date}",
    "kitne drivers active the {date}",
    "fleet me kitna distance cover hua {date}",
    "fleet ka status kya chal raha hai",
    "dashboard ka quick snapshot",
    "fleet metrics",
    "overall trip count for {date}",
    "average fleet speed {date}",
    "fleet performance report for {date}",
    "fleet me kitne vehicles active hain",
    "fleet ka avg speed aur ETA rate batao",
    "fleet ka monthly report chahiye",
    "how many alerts generated {date}",
    "give me fleet KPIs for presentation",
    "overall system performance batao",
    "fleet ka workload kitna hai {date}",
    "fleet ka pura data dikhao {date}",
    "show fleet comparison {date}",
    "fleet ka score batao overall",
    "aaj fleet ka kaisa raha performance",
    "fleet efficiency {date}",
    "total distance aur trips {date}",
    "fleet ka ek line summary",
    "fleet ka quick check karo",
    "fleet operational summary {date}",
    "fleet health report {date}",
    "fleet activity breakdown {date}",
    "show busiest day {date}",
    "fleet capacity utilization {date}",
    "fleet me total kitna kaam hua {date}",
    "fleet stats overview chahiye",
    "fleet ka report short me de do",
    "show me overall fleet numbers",
    "fleet trend analysis for {date}",
    "kitna load handle hua fleet me {date}",
    "fleet ka data simple me batao",
    "I need to prepare fleet report for {date}",
    "give fleet summary for management meeting",
    "fleet ka kya haal hai {date}",
    "fleet dashboard data pull karo",
    "how many vehicles ran {date}",
    "total kilometers {date}",
    "fleet speed trend {date}",
    "shwo fleet sumary",
    "flet stats {date}",
    "fleeet performance dikhao",
]

TEMPLATES["driver_performance"] = [
    "show {driver} performance",
    "driver {did} ka score kya hai",
    "{driver} ka performance trend dikhao",
    "how many trips has {driver} completed",
    "driver {did} ka driving pattern kya hai",
    "compare top {num} drivers by score",
    "list all high risk drivers",
    "driver performance report generate karo",
    "{driver} ka monthly trend",
    "driver {did} ke trips kitne hain",
    "who are lowest performing drivers",
    "driver {did} ka score breakdown",
    "show driving pattern for {driver}",
    "driver ranking by consistency",
    "top drivers by efficiency",
    "driver ka avg speed kya hai {driver} ka",
    "{driver} ki performance kaisi hai",
    "driver {did} trend for {date}",
    "{driver} ka composite score",
    "driver scores list karo",
    "driver {did} vehicles kitne use kiye",
    "{driver} frequent routes kya hain",
    "driver {did} ETA success rate",
    "show all drivers with score below 50",
    "driver {did} ka performance {date}",
    "{driver} performance compared to fleet average",
    "driver {did} speed distribution",
    "{driver} ka risk level kya hai",
    "driver {did} hourly driving pattern",
    "driver experience ranking",
    "{driver} ka recent performance kaisa hai",
    "driver {did} ka efficiency score",
    "drivers with most trips {date}",
    "{driver} ka consistency score",
    "driver {did} day of week pattern",
    "bottom {num} drivers by performance",
    "{driver} ka trip count aur score",
    "driver {did} performance graph dikhao",
    "how is {driver} doing",
    "driver {did} ka kya haal hai",
    "{driver} ne {date} me kitne trips kiye",
    "driver ranking overall",
    "driver {did} ka detailed profile",
    "{driver} ki speed kaisi hai",
    "driver {did} ka trend up hai ya down",
    "show me worst performing drivers",
    "driver {did} performance summary",
    "{driver} ka complete analysis",
    "which driver has best score",
    "driver {did} ka ETA compliance kya hai",
    "{driver} ke recent trips dikhao",
    "driver scoring report for {date}",
    "driver {did} ka kaam kaisa chal raha",
    "{driver} vs {driver} compare karo",
    "driver {did} ka performance normal hai ya nahi",
    "{driver} ka data ekdum simple batao",
    "driver ka performance weak hai kya check karo {did}",
    "drivr perfomance for {driver}",
    "drivr {did} scor",
    "{driver} ka perfomance",
]

TEMPLATES["trip_management"] = [
    "show me trip {trip}",
    "list all trips from {origin} to {dest} {date}",
    "how many active trips right now",
    "find completed trips for driver {did} in {date}",
    "trip details for {trip}",
    "show trips with ETA missed {date}",
    "what was the duration of trip {trip}",
    "list all trips for vehicle {vehicle}",
    "trips from {origin} to {dest} {date}",
    "trip {trip} ka status kya hai",
    "show all completed trips {date}",
    "trip history for driver {did}",
    "trip {trip} waypoints dikhao",
    "active trips kitne hain abhi",
    "trip search from {origin}",
    "trip {trip} me kitna time laga",
    "list delayed trips {date}",
    "trip details for dispatch DIS-2026-{trip}",
    "trips filtered by vehicle {vehicle}",
    "show trips between {origin} and {dest}",
    "trip {trip} ki details batao",
    "total active trips count",
    "trip {trip} driver kaun tha",
    "find trip by vehicle {vehicle} {date}",
    "trip stats overall",
    "how many trips completed {date}",
    "trip {trip} route details",
    "search trips for {driver}",
    "trip duration for {trip}",
    "list all in-progress trips",
    "trip {trip} ka speed kaisa tha",
    "filter trips by status completed {date}",
    "show delayed trips from {origin}",
    "trip {trip} comparison with route average",
    "all trips on {route} route {date}",
    "trip {trip} me delay hua kya",
    "trips for {driver} vehicle {vehicle}",
    "how many trips from {origin} {date}",
    "trip {trip} actual vs estimated time",
    "latest trips list karo",
    "trip history for {date}",
    "trip {trip} ki puri info do",
    "show trip {trip} waypoint map",
    "pending trips list",
    "trips to {dest} {date}",
    "cancelled trips {date}",
    "trip {trip} origin destination kya tha",
    "trip count by status {date}",
    "recent trips dikhao",
    "trip {trip} ka result kya hua",
    "find trips taking more than 10 hours {date}",
    "trip {trip} vehicle kaun sa tha",
    "trips from {origin} to {dest} for {driver}",
    "show longest trips {date}",
    "shortest trips {date}",
    "trip {trip} delay kitna hua",
    "search trip {trip}",
    "trip {trip} ka data pull karo",
    "trp {trip} details",
    "show me trp {trip}",
    "trip list for {date}",
    "all trips {date} filter by origin {origin}",
    "trip listing page {num}",
]

TEMPLATES["route_intelligence"] = [
    "performance of {route} route",
    "which route has the worst ETA success rate",
    "time pattern analysis for {route}",
    "best time of day to dispatch on {route} route",
    "compare {origin}-{dest} vs {origin}-{dest} routes",
    "top drivers on the {route} route",
    "average duration on {route} route",
    "show route performance sorted by ETA success",
    "which day of week is best for {route} route",
    "{route} route ka performance kaisa hai",
    "route analysis for {origin} to {dest}",
    "route {origin} to {dest} avg duration",
    "best performing route overall",
    "worst performing routes {date}",
    "route ETA success rate comparison",
    "time of day pattern for {route}",
    "route {origin} to {dest} me kitne trips hue {date}",
    "{route} route ka avg speed kya hai",
    "show route rankings by trip count",
    "day of week pattern for {route}",
    "{route} route ka trend kaisa hai",
    "route performance breakdown for {origin} to {dest}",
    "hourly pattern for {route} route",
    "which route is most reliable",
    "route {origin} to {dest} top {num} drivers",
    "route comparison {date}",
    "route {origin} to {dest} recent trips performance",
    "fastest routes list",
    "slowest routes list",
    "{origin} to {dest} route stats",
    "route {origin} to {dest} me best time kya hai",
    "show routes with worst performance {date}",
    "route ka time analysis {origin} to {dest}",
    "route performance for {date}",
    "which route has most delays",
    "route {origin} to {dest} ka ETA rate kya hai",
    "best day to dispatch on {route}",
    "route efficiency ranking",
    "route {origin} to {dest} hourly breakdown",
    "route {origin} to {dest} ka pura analysis",
    "route detail for {origin} to {dest}",
    "top {num} routes by performance",
    "bottom {num} routes by ETA success",
    "route {origin} to {dest} weekday vs weekend",
    "route me delays kab hote hain {origin} to {dest}",
    "route ka performance graph {origin} to {dest}",
    "route intelligence for {origin} to {dest}",
    "route ka data dikhao {origin} to {dest}",
    "compare top {num} routes side by side",
    "route {origin} to {dest} performance {date}",
    "which route runs best on {day}",
    "route analysis for {day} dispatch",
    "route ka weekly pattern {origin} to {dest}",
    "roue perfomance {origin} to {dest}",
    "rout stats {origin} {dest}",
]

TEMPLATES["vehicle_tracking"] = [
    "show details for vehicle {vehicle}",
    "which vehicles have the highest mileage",
    "list all trips for vehicle {vehicle}",
    "how many drivers used vehicle {vehicle}",
    "vehicle utilization report",
    "monthly trend for vehicle {vehicle}",
    "which vehicles are underperforming",
    "show vehicle fleet sorted by total trips",
    "what routes does vehicle {vehicle} usually cover",
    "vehicle {vehicle} ka status kya hai",
    "vehicle {vehicle} performance kya hai",
    "vehicle {vehicle} ki details dikhao",
    "vehicle {vehicle} kitne trips kiye {date}",
    "vehicle performance report {date}",
    "vehicle {vehicle} drivers list",
    "vehicle {vehicle} avg speed",
    "vehicle {vehicle} ETA success rate",
    "vehicle {vehicle} total distance",
    "top {num} vehicles by utilization",
    "vehicle fleet summary",
    "vehicle {vehicle} recent trips",
    "vehicle {vehicle} route history",
    "worst performing vehicles",
    "vehicle {vehicle} me kaun kaun driver chala",
    "vehicle comparison top {num}",
    "show all vehicles {date}",
    "vehicle {vehicle} trip history {date}",
    "vehicle {vehicle} ka monthly breakdown",
    "vehicle ka data {vehicle}",
    "which vehicle has most trips {date}",
    "vehicle {vehicle} health check",
    "vehicle {vehicle} performance {date}",
    "vehicle {vehicle} ka trend up ya down",
    "vehicle list with performance metrics",
    "vehicle {vehicle} ka complete report",
    "vehicle search {vehicle}",
    "vehicle {vehicle} benchmarks vs fleet",
    "vehicle {vehicle} underperforming hai kya",
    "bottom {num} vehicles by performance",
    "vehicle {vehicle} ka efficiency",
    "vehicle ka overview fleet me",
    "vehicle {vehicle} driver history",
    "most used vehicles {date}",
    "least used vehicles {date}",
    "vehicle {vehicle} ka data pull karo",
    "vehicle fleet ka breakdown dikhao",
    "vehicle {vehicle} maintenance status",
    "vehicl {vehicle} details",
    "vehcle {vehicle} trips",
    "vehicle {vehicle} aaj kitna chala",
    "vehicle {vehicle} ka speed data",
    "vehicle {vehicle} kitne routes cover karta hai",
    "vehicle {vehicle} ka distance {date}",
    "show vehicle {vehicle} complete profile",
    "vehicle {vehicle} performance graph",
    "vehicle {vehicle} vs fleet average",
    "vehicle {vehicle} me koi issue hai kya",
    "all vehicles sorted by distance {date}",
    "vehicle report for management {date}",
    "kitne vehicles active hain {date}",
]

TEMPLATES["eta_sla_prediction"] = [
    "predict ETA for a trip from {origin} to {dest}",
    "how long will it take from {origin} to {dest} with driver {did}",
    "on-time probability for {origin} to {dest} tomorrow morning",
    "will driver {driver} deliver on time from {origin} to {dest}",
    "SLA prediction for trip starting at {hour} from {origin} to {dest}",
    "estimate delivery time for vehicle {vehicle} from {origin} to {dest}",
    "risk of delay for {route} route at {hour}",
    "predict trip duration for {dist} journey from {origin} to {dest}",
    "ETA prediction {origin} to {dest}",
    "{origin} se {dest} jane me kitna time lagega",
    "predict karo {origin} to {dest} ka ETA",
    "will this trip be on time {origin} to {dest}",
    "on time probability kya hai {route}",
    "SLA check for {origin} to {dest} with {driver}",
    "ETA for {origin} to {dest} at {hour} on {day}",
    "delay risk assessment {origin} to {dest}",
    "predict arrival time {origin} to {dest}",
    "estimated time for {route} route",
    "will driver {did} make it on time to {dest}",
    "trip duration prediction for {origin} to {dest}",
    "{origin} to {dest} predicted time with vehicle {vehicle}",
    "SLA forecast for {route}",
    "{driver} ka {origin} to {dest} pe predicted time",
    "ETA estimate for {dist} trip",
    "on time delivery probability for {route}",
    "predict delay for {origin} to {dest} {day} {hour}",
    "how long for {origin} to {dest} trip",
    "estimated arrival {origin} to {dest}",
    "will {driver} reach {dest} on time",
    "SLA risk for {origin} to {dest} at {hour}",
    "{origin} se {dest} ka estimated time batao",
    "trip time prediction {route}",
    "predict karo delay hoga ya nahi {origin} to {dest}",
    "ETA for {driver} going {origin} to {dest}",
    "{origin} to {dest} time estimate for {day}",
    "SLA prediction with driver {did} vehicle {vehicle}",
    "predict {route} duration at {hour}",
    "delivery time forecast {origin} to {dest}",
    "on time ya late hoga {origin} to {dest}",
    "{origin} to {dest} ka ETA kya hai with {driver}",
    "time lagega kitna {origin} to {dest}",
    "predict duration {origin} to {dest} {dist}",
    "SLA check karo {route} ke liye",
    "eta predicton {origin} to {dest}",
    "eta predction for {route}",
    "perdiction for {origin} {dest} trip",
    "how much time {origin} to {dest} at {hour}",
    "trip time estimate {origin} to {dest} with {driver}",
    "delay probability {route} at {hour}",
    "predict if trip {origin} to {dest} will be on time",
    "expected duration {origin} to {dest}",
    "SLA for upcoming trip {origin} to {dest}",
    "{driver} {origin} se {dest} tak kitne ghante",
    "arrival prediction for vehicle {vehicle} to {dest}",
    "predict {origin} to {dest} morning trip ETA",
    "night trip ETA {origin} to {dest} at {hour}",
    "ETA if we dispatch at {hour} from {origin} to {dest}",
    "will {origin} to {dest} trip meet SLA with {driver}",
    "predict timing for {origin} to {dest} via {origin}",
    "time forecast {origin} to {dest}",
]

TEMPLATES["anomaly_alert"] = [
    "scan last {num} days for anomalies",
    "are there any unusual trips {date}",
    "show recent alerts",
    "how many high-severity anomalies were detected",
    "scan for anomalies in trips from {origin}",
    "any suspicious trip patterns {date}",
    "show critical alerts",
    "check if there are any outlier trips {date}",
    "what anomalies were found in the last scan",
    "run anomaly detection on {date}",
    "any trips that took unusually long {date}",
    "anomaly scan karo {date}",
    "koi unusual trip hai kya {date}",
    "alerts dikhao recent wale",
    "high severity alerts {date}",
    "anomaly detection run karo last {num} days",
    "suspicious activities {date}",
    "outlier trips list karo",
    "any red flags in trips {date}",
    "scan trips for issues {date}",
    "anomalies on {origin} to {dest} route",
    "alert summary {date}",
    "trip anomalies for driver {did}",
    "unusual patterns detected kya {date}",
    "koi alert aaya hai kya recently",
    "anomaly scan results dikhao",
    "scan for unusual trip durations {date}",
    "any trips with abnormal speed {date}",
    "check anomalies for vehicle {vehicle}",
    "alert severity breakdown {date}",
    "how many anomalies found {date}",
    "scan trips on {route} for issues",
    "unusual delay patterns {date}",
    "flag suspicious trips {date}",
    "anomaly report {date}",
    "run full anomaly scan",
    "trip outlier detection {date}",
    "any warnings or alerts {date}",
    "koi problem hai kya trips me {date}",
    "anomaly check karo {origin} to {dest}",
    "scan recent trips for issues",
    "alert count {date}",
    "trip duration anomalies {date}",
    "speed anomalies {date}",
    "show flagged trips {date}",
    "anomaly detection for {date} trips",
    "koi unusual cheez mili kya scan me",
    "alert dashboard dikhao",
    "critical anomalies list {date}",
    "medium severity alerts {date}",
    "check for trip irregularities {date}",
    "anomaly scan for driver {driver} trips",
    "scan {origin} route trips for anomalies",
    "unusual trip patterns on {route}",
    "anomlay scan {date}",
    "anamoly detection run karo",
    "any alerts for vehicle {vehicle}",
    "unusual activity {date} detected kya",
    "scan karo koi issue hai kya {date}",
    "problematic trips {date}",
    "trip quality check {date}",
    "show all unacknowledged alerts",
    "acknowledge alert for trip {trip}",
]

TEMPLATES["demand_forecasting"] = [
    "how many trips expected next week on {route}",
    "demand forecast for {route} route",
    "fleet-wide trip prediction for next 7 days",
    "is demand growing or declining on {route}",
    "client forecast for {client}",
    "how many trips will {client} need next week",
    "show demand trend for top {num} routes",
    "seasonal pattern for {route} demand",
    "predict next week trip volume",
    "which routes will be busiest next week",
    "client profile for {client}",
    "demand prediction {route}",
    "{route} route pe kitne trips honge next week",
    "trip volume forecast for {date}",
    "{client} ka demand kitna hoga",
    "demand trend for {origin} to {dest}",
    "weekly demand forecast",
    "trip forecast route wise",
    "demand growing hai ya down hai {route}",
    "{client} ka trip pattern kya hai",
    "next 7 days me kitne trips honge",
    "route demand comparison next week",
    "{client} forecast next month",
    "demand for {origin} routes",
    "trip volume prediction {date}",
    "{client} ka weekly avg trips kitna hai",
    "forecast {route} demand for {date}",
    "busiest routes next week prediction",
    "client {client} trip demand",
    "demand analysis for {route}",
    "how many trips to {dest} expected next week",
    "fleet demand forecast",
    "{client} growth rate kya hai",
    "seasonal demand pattern for {route}",
    "trip count prediction {route} next {num} days",
    "demand for {origin} to {dest} route {date}",
    "client demand breakdown {date}",
    "{client} ka top routes kya hain",
    "demand forecast report for management",
    "which route will see growth next month",
    "{client} monthly demand trend",
    "predicted trip volume for {route}",
    "forecast demand from {origin}",
    "how busy will {route} be next week",
    "trip demand rising ya falling {route}",
    "{client} ka seasonal pattern",
    "demand prediction for top {num} clients",
    "next month ka demand estimate",
    "route wise demand forecast {date}",
    "{client} ka future demand predict karo",
    "forcast for {route}",
    "demnd forecast {route}",
    "demand predction {origin} to {dest}",
    "client {client} demand for next week",
    "trip volume for {origin} to {dest} next {num} days",
    "demand trend report {date}",
    "expected trips on {route} {day}",
    "client wise demand comparison {date}",
    "top {num} growing routes by demand",
    "declining demand routes list",
]

TEMPLATES["route_optimization"] = [
    "best route from {origin} to {dest}",
    "optimize route from {origin} to {dest}",
    "which driver should I assign for {route}",
    "recommend top {num} drivers for {route} route",
    "find alternative routes from {origin} to {dest}",
    "what are the major hub locations",
    "suggest the fastest route from {origin} to {dest}",
    "who is the best driver for the {route} route",
    "multi-stop route from {origin} to {dest} via {origin}",
    "which drivers have experience on {route} route",
    "{origin} se {dest} ka best route kya hai",
    "route optimize karo {origin} to {dest}",
    "best driver kaun hai {route} ke liye",
    "recommend driver for {origin} to {dest}",
    "alternative routes {origin} to {dest}",
    "hub locations dikhao",
    "fastest way from {origin} to {dest}",
    "driver recommendation for {route}",
    "optimal path {origin} to {dest}",
    "which driver best for {origin} to {dest} at {hour}",
    "route plan {origin} to {dest}",
    "suggest drivers for {route} route",
    "best route at {hour} from {origin} to {dest}",
    "multi hop route {origin} to {dest}",
    "experienced drivers on {route}",
    "assign driver for {origin} to {dest}",
    "route optimize for {day} {origin} to {dest}",
    "who should drive {origin} to {dest}",
    "plan route from {origin} to {dest}",
    "route suggestion {origin} to {dest}",
    "driver match for {route}",
    "find best path {origin} to {dest}",
    "route options {origin} to {dest}",
    "driver {driver} suitable hai kya {route} ke liye",
    "kaun driver bhejein {origin} to {dest}",
    "route me stops chahiye {origin} to {dest}",
    "transit hub analysis",
    "warehouse hub locations",
    "key hub points in network",
    "route optimizer run karo {origin} to {dest}",
    "best time and route for {origin} to {dest}",
    "recommend route and driver for {origin} to {dest}",
    "optimal dispatch plan {origin} to {dest}",
    "which route is faster {origin} to {dest}",
    "shortest route {origin} to {dest}",
    "roue optimization {origin} to {dest}",
    "optmize rout {origin} {dest}",
    "route plan with stops from {origin} to {dest}",
    "driver allocation for {route}",
    "assign best resources for {origin} to {dest}",
    "route planning for {day} dispatch",
    "network hub identification",
    "top intermediate stops between {origin} and {dest}",
    "recommend most experienced driver for {route}",
    "optimal route considering time {hour} from {origin}",
    "efficient path from {origin} to {dest}",
    "driver ranking for {route} route",
    "best available driver for {origin} to {dest} now",
    "route + driver recommendation {origin} to {dest}",
]

TEMPLATES["driver_safety"] = [
    "check fatigue risk for driver {driver}",
    "which drivers are at critical fatigue risk",
    "show fleet-wide fatigue summary",
    "how many hours has driver {did} driven in last 24 hours",
    "night trip count for {driver} this week",
    "is driver {did} safe to dispatch right now",
    "drivers who worked more than 5 consecutive days",
    "show top {num} most fatigued drivers",
    "rest compliance check for all drivers",
    "safety dashboard",
    "who should not be driving today",
    "driver workload analysis",
    "{driver} fatigue risk kya hai",
    "driver {did} kitne ghante drive kiya {date}",
    "{driver} ko rest chahiye kya",
    "fatigue check for driver {did}",
    "driver safety report {date}",
    "is {driver} overworked",
    "driver {did} consecutive days active",
    "{driver} night trips {date}",
    "fatigue probability for driver {did}",
    "driver {did} ka fatigue score",
    "kya {driver} ko bhej sakte hain abhi trip pe",
    "driver rest status check",
    "fleet fatigue summary",
    "critical fatigue risk drivers list",
    "driver {did} workload {date}",
    "{driver} ka safety status",
    "driver hours driven {did} {date}",
    "fatigued drivers list {date}",
    "who is too tired to drive",
    "driver {did} last rest kab liya",
    "{driver} ka driving hours {date}",
    "safety alert for driver {did}",
    "driver fatigue report generate karo",
    "overworked drivers {date}",
    "driver {did} speed variance {date}",
    "{driver} ki safety risk kya hai",
    "driver {did} trip load {date}",
    "show drivers with high fatigue score",
    "driver {did} night driving {date}",
    "{driver} ko aaj bhej sakte hain kya",
    "driver {did} safe hai kya dispatch ke liye",
    "fatigue monitoring dashboard",
    "driver rest compliance {date}",
    "how many drivers overworked {date}",
    "driver {did} ka stress level",
    "{driver} ke liye safety check karo",
    "driver {did} recent workload analysis",
    "driver hours report {date}",
    "who needs rest urgently",
    "fatigue risk fleet overview",
    "driver {did} driving pattern safety check",
    "{driver} ka fatigue level check karo",
    "driver {did} continuous driving hours",
    "safety compliance report {date}",
    "driver {driver} ko rest do ya dispatch karo",
    "driver {did} thak gaya hai kya",
    "fatgue check {driver}",
    "fatige risk {did}",
    "driver safety status {driver}",
    "consecutive duty days driver {did}",
    "night shift drivers {date}",
    "driver burnout risk {did}",
    "driver {did} weekly hours breakdown",
    "{driver} fit hai trip ke liye ya nahi",
]


# ── Augmentation helpers ──────────────────────────────────────────────────────

FILLER_PREFIXES = [
    "can you ", "please ", "I want to ", "I need to ", "could you ",
    "hey ", "bhai ", "yaar ", "quickly ", "just ",
    "help me ", "I'd like to ", "show me ", "tell me ", "give me ",
]

FILLER_SUFFIXES = [
    " please", " asap", " quickly", " now", " urgently",
    " for me", " right now", " jaldi", " abhi", "",
    " if possible", " when you can", " thanks", "",
]


def augment_query(query):
    """Apply random light augmentation to an existing query."""
    q = query.strip().strip('"')
    choice = random.random()

    if choice < 0.25:
        # Add a prefix
        prefix = random.choice(FILLER_PREFIXES)
        q = prefix + q[0].lower() + q[1:]
    elif choice < 0.45:
        # Add a suffix
        suffix = random.choice(FILLER_SUFFIXES)
        q = q.rstrip("?. ") + suffix
    elif choice < 0.60:
        # Random word deletion (drop 1 word if length > 4)
        words = q.split()
        if len(words) > 4:
            idx = random.randint(1, len(words) - 2)
            words.pop(idx)
            q = " ".join(words)
    elif choice < 0.75:
        # Swap two adjacent words
        words = q.split()
        if len(words) > 3:
            idx = random.randint(0, len(words) - 2)
            words[idx], words[idx + 1] = words[idx + 1], words[idx]
            q = " ".join(words)
    elif choice < 0.85:
        # Lowercase everything
        q = q.lower()
    elif choice < 0.92:
        # Add typo (duplicate a random character)
        if len(q) > 5:
            idx = random.randint(2, len(q) - 2)
            q = q[:idx] + q[idx] + q[idx:]
    else:
        # Rephrase slightly - add "bhai" or "yaar" or "na"
        q = q + random.choice([" bhai", " yaar", " na", " check karo", " batao"])

    return q


# ── Main balancing logic ──────────────────────────────────────────────────────

def main():
    # Step 1: Read and clean existing data
    existing = {}  # agent -> list of queries
    with open("dataset.txt", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) >= 2:
                agent = row[1].strip()
                query = row[0].strip().strip('"')
                if agent and agent != "agent" and query:
                    if agent not in existing:
                        existing[agent] = []
                    existing[agent].append(query)

    print("=== BEFORE BALANCING ===")
    total_before = 0
    for agent in sorted(existing.keys()):
        count = len(existing[agent])
        total_before += count
        deficit = max(0, TARGET_PER_CLASS - count)
        print(f"  {agent:<25s}: {count:>5d}  (need {deficit} more)")
    print(f"  {'TOTAL':<25s}: {total_before:>5d}")

    # Step 2: Generate new rows to balance
    all_queries_set = set()
    for queries in existing.values():
        for q in queries:
            all_queries_set.add(q.lower().strip())

    balanced = {}
    for agent, queries in existing.items():
        balanced[agent] = list(queries)  # copy existing

        deficit = TARGET_PER_CLASS - len(queries)
        if deficit <= 0:
            continue

        templates = TEMPLATES.get(agent, [])
        if not templates:
            print(f"  WARNING: No templates for {agent}, using augmentation only")

        generated = 0
        attempts = 0
        max_attempts = deficit * 20  # safety valve

        while generated < deficit and attempts < max_attempts:
            attempts += 1

            # 60% from templates, 40% from augmenting existing
            if templates and random.random() < 0.6:
                template = random.choice(templates)
                new_query = fill(template)
            else:
                base = random.choice(queries)
                new_query = augment_query(base)

            # Deduplicate
            key = new_query.lower().strip()
            if key not in all_queries_set and len(new_query) > 5:
                all_queries_set.add(key)
                balanced[agent].append(new_query)
                generated += 1

        if generated < deficit:
            print(f"  WARNING: {agent} only generated {generated}/{deficit} (template exhaustion)")

    # Step 3: Write balanced dataset
    print("\n=== AFTER BALANCING ===")
    total_after = 0
    all_rows = []
    for agent in sorted(balanced.keys()):
        count = len(balanced[agent])
        total_after += count
        print(f"  {agent:<25s}: {count:>5d}")
        for query in balanced[agent]:
            all_rows.append((query, agent))

    print(f"  {'TOTAL':<25s}: {total_after:>5d}")

    # Step 4: Deduplicate (case-insensitive)
    print("\n=== DEDUPLICATING ===")
    seen = set()
    deduped = {}  # agent -> list of unique queries
    dup_count = 0
    for query, agent in all_rows:
        key = query.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.setdefault(agent, []).append(query)
        else:
            dup_count += 1
    print(f"  Removed {dup_count} duplicates")

    # Step 5: Re-fill any class that dropped below target
    for agent in sorted(deduped.keys()):
        deficit = TARGET_PER_CLASS - len(deduped[agent])
        if deficit <= 0:
            continue
        print(f"  Re-filling {agent}: need {deficit} more after dedup")
        templates = TEMPLATES.get(agent, [])
        base_queries = deduped[agent]
        generated = 0
        attempts = 0
        while generated < deficit and attempts < deficit * 30:
            attempts += 1
            if templates and random.random() < 0.5:
                new_query = fill(random.choice(templates))
            else:
                new_query = augment_query(random.choice(base_queries))
            key = new_query.lower().strip()
            if key not in seen and len(new_query) > 5:
                seen.add(key)
                deduped[agent].append(new_query)
                generated += 1

    # Rebuild all_rows from deduped
    all_rows = []
    for agent in sorted(deduped.keys()):
        for query in deduped[agent]:
            all_rows.append((query, agent))

    # Shuffle
    random.shuffle(all_rows)

    # Final stats
    print("\n=== FINAL BALANCED DATASET ===")
    total_final = 0
    for agent in sorted(deduped.keys()):
        count = len(deduped[agent])
        total_final += count
        print(f"  {agent:<25s}: {count:>5d}")
    print(f"  {'TOTAL':<25s}: {total_final:>5d}")

    # Write CSV
    with open("dataset_balanced.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["query", "agent"])
        for query, agent in all_rows:
            writer.writerow([query, agent])

    print(f"\nSaved to dataset_balanced.csv ({len(all_rows)} rows)")


if __name__ == "__main__":
    main()
