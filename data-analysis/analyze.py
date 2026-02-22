import pandas as pd
import sys

# Read CSV in chunks to handle large files
file_path = 'data/tbl_trip_data20260128.csv'  # Replace with your file path

try:
    # Try reading first 100 rows with different encodings
    for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
        try:
            df = pd.read_csv(file_path, nrows=100, encoding=encoding, on_bad_lines='skip')
            print(f"Success with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            continue

    # Basic analysis
    print("\n=== SHAPE ===")
    print(f"Rows: {len(df)}, Columns: {len(df.columns)}")

    print("\n=== COLUMNS ===")
    print(df.columns.tolist())

    print("\n=== DATA TYPES ===")
    print(df.dtypes)

    print("\n=== NULL VALUES ===")
    print(df.isnull().sum())

    print("\n=== FIRST 5 ROWS ===")
    print(df.head())

    print("\n=== BASIC STATS ===")
    print(df.describe())

    # Identify dead columns (all null or single value)
    dead_cols = []
    for col in df.columns:
        if df[col].isnull().all():
            dead_cols.append(col)
        elif df[col].nunique() == 1:
            dead_cols.append(col)

    print("\n=== DEAD COLUMNS ===")
    print(dead_cols)

    # Save cleaned data
    df_clean = df.drop(columns=dead_cols)
    df_clean.to_csv('cleaned_top100.csv', index=False)
    print("\n✓ Saved cleaned data to 'cleaned_top100.csv'")

except Exception as e:
    print(f"Error: {e}")