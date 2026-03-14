# %%
## Initialization
import sqlite3
from tqdm import tqdm
from pathlib import Path
import pandas as pd
import subprocess
import re

# =============================================================================
# CONFIGURATION
# =============================================================================

DRIVE_PATH = "./drive/MyDrive/db"
IS_COLAB = Path(DRIVE_PATH).exists()

DB_PATH = "web_data.db"
DATA_DIR = Path("data")
REPORT_PATH = DATA_DIR / "report_data.parquet"
NAMES_PATH = DATA_DIR / "names_export.parquet"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _ensure_data_dir():
    """Creates the data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_file_is_local(file_pattern: str) -> list[Path]:
    """
    Checks for files matching a pattern locally. If not found and in Colab,
    copies them from Google Drive.

    Args:
        file_pattern (str): The file name or glob pattern to look for.

    Returns:
        list[Path]: A list of local paths to the found files, or an empty list if none are found.
    """
    local_files = list(Path(".").glob(file_pattern))

    if local_files:
        print(f"  -> Found {len(local_files)} matching file(s) locally.")
        return local_files

    if IS_COLAB:
        print(f"  -> No local files found. Checking Google Drive: '{DRIVE_PATH}'...")
        drive_files = list(Path(DRIVE_PATH).glob(file_pattern))

        if not drive_files:
            print("  -> ❌ No matching files found in Google Drive either.")
            return []

        print(
            f"  -> Found {len(drive_files)} file(s) in Google Drive. Copying locally..."
        )
        copied_files = []
        for drive_file in tqdm(drive_files, desc="  Copying from Drive"):
            local_dest = Path(".") / drive_file.name
            try:
                subprocess.run(
                    ["cp", str(drive_file), str(local_dest)],
                    check=True,
                    capture_output=True,
                )
                copied_files.append(local_dest)
            except subprocess.CalledProcessError as e:
                print(f"  -> ❌ Error copying {drive_file.name}: {e.stderr.decode()}")
            except Exception as e:
                print(f"  -> ❌ Unexpected error copying {drive_file.name}: {e}")

        if not copied_files:
            print("  -> ❌ No files were successfully copied from Drive.")

        return copied_files

    return []


def execute_sql(sql: str, head: int = 0) -> pd.DataFrame | int:
    """
    Execute a SQL statement on the SQLite database.

    Parameters
    ----------
    sql : str
        SQL statement to execute.
    head : int, default 0
        If the query is a SELECT and head > 0, return only the first `head` rows.

    Returns
    -------
    pd.DataFrame or int
        DataFrame for SELECT queries; row count for write operations.
    """
    if not _ensure_file_is_local(DB_PATH):
        print(f"❌ Cannot execute SQL: Database file '{DB_PATH}' not found.")
        return -1

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    is_select = sql.strip().upper().startswith("SELECT")

    try:
        cursor.execute(sql)
        if is_select:
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()
            df = pd.DataFrame(data, columns=columns)
            return df.head(head) if head > 0 else df
        else:
            conn.commit()
            return cursor.rowcount
    finally:
        conn.close()


def extract_accession(url):
    """Extracts an 18-digit accession number from a URL."""
    if not isinstance(url, str):
        return None
    match = re.search(r"/(\d{18})/", url)
    return match.group(1) if match else None


def _format_accession(series: pd.Series) -> pd.Series:
    """Ensures accession numbers are zero-padded 18-character strings."""
    return series.apply(
        lambda x: str(int(float(x))).zfill(18) if pd.notna(x) and x != "" else None
    )


# =============================================================================
# IMPORT / EXPORT
# =============================================================================


def import_report_data():
    """
    Imports report_data and names from parquet files in the data/ directory
    into the SQLite database.
    """
    print(f"\n[1/3] Searching for '{REPORT_PATH}'...")
    files = _ensure_file_is_local(str(REPORT_PATH))

    if not files:
        print(f"  -> ❌ No report data file found to import.")
        return

    print(f"\n[2/3] Reading '{files[0]}'...")
    try:
        df = pd.read_parquet(files[0])
        if "accession" in df.columns:
            df["accession"] = df["accession"].astype(str)
        print(f"  -> Found {len(df):,} records.")
    except Exception as e:
        print(f"  -> ❌ Error reading parquet file: {e}")
        return

    if not {"cik", "year", "url"}.issubset(df.columns):
        print("  -> ❌ File is missing required columns: 'cik', 'year', or 'url'.")
        return

    print(f"\n[3/3] Connecting to database '{DB_PATH}'...")
    conn = sqlite3.connect(DB_PATH)
    try:
        # --- Names ---
        names_files = _ensure_file_is_local(str(NAMES_PATH))
        if names_files:
            print(f"  -> Importing names from '{NAMES_PATH}'...")
            try:
                names_df = pd.read_parquet(names_files[0])
                if {"cik", "name"}.issubset(names_df.columns):
                    names_df = names_df[["cik", "name"]].dropna().drop_duplicates()
                    names_df.to_sql("names", conn, if_exists="replace", index=False)
                    conn.execute("CREATE INDEX IF NOT EXISTS name_idx ON names (name)")
                    print(f"     ✅ Imported {len(names_df):,} names.")
            except Exception as e:
                print(f"     ❌ Error importing names: {e}")
        elif "name" in df.columns:
            print("  -> Importing names from report data (fallback)...")
            names_df = df[["cik", "name"]].dropna().drop_duplicates()
            names_df.to_sql("names", conn, if_exists="replace", index=False)
            conn.execute("CREATE INDEX IF NOT EXISTS name_idx ON names (name)")

        # --- Report Data ---
        print("  -> Preparing report_data...")
        if "accession" not in df.columns:
            df["accession"] = df["url"].apply(extract_accession)
        else:
            df["accession"] = _format_accession(df["accession"])

        if "original_url" not in df.columns:
            df["original_url"] = df["url"]

        report_df = (
            df[["cik", "year", "url", "accession", "original_url"]]
            .dropna(subset=["cik", "year", "url"])
            .drop_duplicates()
        )

        report_df.to_sql("report_data", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS url_idx ON report_data (url)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS report_acc_idx ON report_data (accession)"
        )

        print(f"     ✅ Imported {len(report_df):,} rows into report_data.")
        print("\n✅ Import successful.")
    except Exception as e:
        print(f"  -> ❌ A database error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()


def export_data():
    """
    Exports the report_data and names tables from the SQLite database
    to parquet files in the data/ directory.
    """
    print(f"\nExporting data from '{DB_PATH}'...")
    if not Path(DB_PATH).exists():
        print(f"❌ Database file '{DB_PATH}' not found.")
        return

    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)

    try:
        # --- Report Data ---
        print("  -> Exporting report_data...")
        try:
            df_report = pd.read_sql("SELECT * FROM report_data", conn)
            if "accession" in df_report.columns:
                df_report["accession"] = _format_accession(df_report["accession"])
            df_report.to_parquet(REPORT_PATH, index=False)
            print(f"     ✅ Saved {len(df_report):,} rows to '{REPORT_PATH}'")
        except Exception as e:
            print(f"     ❌ Error exporting report_data: {e}")

        # --- Names ---
        print("  -> Exporting names...")
        try:
            df_names = pd.read_sql("SELECT * FROM names", conn)
            df_names.to_parquet(NAMES_PATH, index=False)
            print(f"     ✅ Saved {len(df_names):,} rows to '{NAMES_PATH}'")
        except Exception as e:
            print(f"     ❌ Error exporting names: {e}")

    finally:
        conn.close()


def save_db_to_drive():
    """
    Saves the local database file to Google Drive (Colab only).
    """
    if not IS_COLAB:
        print("❌ Not running in Google Colab. Skipping save to Drive.")
        return

    print(f"Saving '{DB_PATH}' to Google Drive at '{DRIVE_PATH}'...")
    cmd = f"cp -f {DB_PATH} {DRIVE_PATH}/{DB_PATH}.tmp && mv -f {DRIVE_PATH}/{DB_PATH}.tmp {DRIVE_PATH}/{DB_PATH}"
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        print(f"✅ Successfully saved '{DB_PATH}' to Google Drive.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error saving to Google Drive: {e.stderr.decode()}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


# =============================================================================
# MAIN INTERACTIVE MENU
# =============================================================================

if __name__ == "__main__":
    df1 = None

    print("\n" + "=" * 50)
    print("        Database Operations Menu")
    print("=" * 50)
    print("1. SELECT * FROM webpage_result")
    print("2. Custom SQL Query")
    print("3. Import report data from parquet")
    print("4. Export report data to parquet")
    print("5. Save database to Google Drive (Colab only)")
    print("6. Inspect last DataFrame")
    print("7. Exit")
    print("-" * 50)

    while True:
        choice = input("Enter your choice: ").strip()

        if choice == "1":
            df = execute_sql("SELECT * FROM webpage_result")
            if isinstance(df, pd.DataFrame):
                df1 = df
                print(df.head(20))
                print("-" * 30)
                print(df.describe())

        elif choice == "2":
            custom_sql = input("Enter your SQL query: ").strip()
            if custom_sql:
                result = execute_sql(custom_sql)
                if isinstance(result, pd.DataFrame):
                    df1 = result
                    print(result)
                    print("-" * 30)
                    print(df1.describe())
                else:
                    print(f"Query executed successfully, {result} rows affected.")
            else:
                print("No SQL query entered.")

        elif choice == "3":
            import_report_data()

        elif choice == "4":
            export_data()

        elif choice == "5":
            save_db_to_drive()

        elif choice == "6":
            if df1 is not None and not df1.empty:
                print("Last DataFrame available as 'df1'. Type 'exit' to return.")
                import code

                code.interact(local=locals())
            else:
                print("No DataFrame loaded yet. Run a query first.")

        elif choice == "7":
            print("Exiting.")
            break

        else:
            print("Invalid choice. Please try again.")

        print("-" * 50)
