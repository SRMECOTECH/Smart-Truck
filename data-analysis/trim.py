import pandas as pd

file_path = 'data/tbl_trip_data20260128.csv'

try:
    for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
        try:
            df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip')
            print(f"Success with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            continue

    # Take first 5 rows
    df_trimmed = df.iloc[:5]

    # 👉 PRINT FIRST 5 ROWS
    print("\n=== FIRST 5 ROWS ===")
    print(df_trimmed)

    # Save
    df_trimmed.to_csv('trimmed.csv', index=False)
    print(f"\n✓ Trimmed {len(df)} → {len(df_trimmed)} rows")
    print("✓ Saved to 'trimmed.csv'")

except Exception as e:
    print(f"Error: {e}")
