import mysql.connector

# Connect to MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="smart_truck"
)

cursor = conn.cursor()

# Get all tables
cursor.execute("SHOW TABLES")
tables = cursor.fetchall()

print("\nDATABASE: smart_truck")
print("="*50)

for table in tables:
    table_name = table[0]
    print(f"\n📌 TABLE: {table_name}")
    print("-"*50)

    # -------- PRINT SCHEMA --------
    print("Schema:")
    cursor.execute(f"DESCRIBE {table_name}")
    schema = cursor.fetchall()

    for col in schema:
        column_name = col[0]
        datatype = col[1]
        null = col[2]
        key = col[3]
        default = col[4]
        extra = col[5]

        print(f"{column_name:20} | {datatype:15} | NULL:{null} | KEY:{key} | DEFAULT:{default}")

    # -------- PRINT 5 ROWS --------
    print("\nFirst 5 rows:")
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
    rows = cursor.fetchall()

    if rows:
        for row in rows:
            print(row)
    else:
        print("No data in table")

    print("="*50)

# Close connection
cursor.close()
conn.close()
