import os

# ============================================
# DATABASE CONFIGURATION
# ============================================

# Database Configuration (Neon PostgreSQL)
# IMPORTANT: No quotes around the connection string!
DATABASE_URL = "postgresql://neondb_owner:npg_i1SF8mhXaWJy@ep-sweet-glade-ai0zyfbt-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

# ============================================
# DATA DIRECTORY CONFIGURATION
# ============================================

# Directory containing CSV/Excel files to import
# Can be relative or absolute path
# Examples:
#   - "Data/split_files"           # Relative path
#   - "C:/Users/YourName/Data"     # Windows absolute path
#   - "/home/user/data"            # Linux absolute path

DATA_DIR = "Data/split_files"  # UPDATE THIS!

# ============================================
# PROCESSING CONFIGURATION
# ============================================

# Batch size for database inserts (adjust based on your data and memory)
BATCH_SIZE = 1000

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL = "INFO"

# ============================================
# ANALYTICS CONFIGURATION
# ============================================

# Minimum trips required for route pattern analysis
MIN_TRIPS_FOR_ROUTE_PATTERN = 3

# Minimum trips required for driver behavior analysis
MIN_TRIPS_FOR_DRIVER_BEHAVIOR = 5

# Top N routes to track per driver
TOP_ROUTES_PER_DRIVER = 5

# Top N performance hours to track per driver
TOP_PERFORMANCE_HOURS = 5