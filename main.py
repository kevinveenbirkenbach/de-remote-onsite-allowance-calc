# app.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

#
# 1) CONFIGURATION / CONSTANTS
#
COLUMNS = [
    "Start",            # YYYY-MM-DDTHH:MM
    "End",              # YYYY-MM-DDTHH:MM
    "Event_Type",       # "work", "travel", or "free"
    "Work_Mode",        # "onsite", "remote", or "free"
    "Remote_Type",      # "domestic", "foreign", or "n/a"
    "Per_Diem_Rate",    # float (€/day)
    "Km_Rate",          # float (€/km)
    "Distance_km",      # float
    "Per_Diem_Total",   # float (computed)
    "Travel_Cost",      # float (computed)
    "Description"       # string
]

DATE_ONLY_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT  = "%Y-%m-%dT%H:%M"

#
# 2) PARSE / VALIDATE FUNCTIONS
#
def parse_datetime(dt_str: str) -> datetime:
    """Accept either 'YYYY-MM-DD' (→ midnight) or 'YYYY-MM-DDTHH:MM'."""
    dt_str = dt_str.strip()
    if len(dt_str) == 10:
        return datetime.strptime(dt_str, DATE_ONLY_FORMAT)
    else:
        return datetime.strptime(dt_str, DATETIME_FORMAT)

def format_datetime(dt_obj: datetime) -> str:
    return dt_obj.strftime(DATETIME_FORMAT)

def recalculate_dataframe(df: pd.DataFrame,
                          inland_rate: float,
                          foreign_rate: float,
                          km_rate: float) -> pd.DataFrame:
    """
    For each row in df, recalculate:
     - Per_Diem_Rate  (depending on Event_Type & Remote_Type)
     - Km_Rate        (if Event_Type == "travel")
     - Per_Diem_Total (days × Per_Diem_Rate)
     - Travel_Cost    (Distance_km × Km_Rate)
     - Description    (auto-fill if blank)
    """
    # Ensure all expected columns exist
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    # Force numeric types
    df["Per_Diem_Rate"]  = pd.to_numeric(df["Per_Diem_Rate"],  errors="coerce").fillna(0.0)
    df["Km_Rate"]        = pd.to_numeric(df["Km_Rate"],        errors="coerce").fillna(0.0)
    df["Distance_km"]    = pd.to_numeric(df["Distance_km"],    errors="coerce").fillna(0.0)
    df["Per_Diem_Total"] = pd.to_numeric(df["Per_Diem_Total"], errors="coerce").fillna(0.0)
    df["Travel_Cost"]    = pd.to_numeric(df["Travel_Cost"],    errors="coerce").fillna(0.0)

    for idx, row in df.iterrows():
        etype = str(row["Event_Type"]).lower().strip()
        wmode = str(row["Work_Mode"]).lower().strip()
        rtype = str(row["Remote_Type"]).lower().strip()

        # Parse start/end → compute days inclusively
        try:
            start_dt = parse_datetime(row["Start"])
            end_dt   = parse_datetime(row["End"])
        except Exception:
            # If parsing fails, skip this row for now
            continue

        days = (end_dt.date() - start_dt.date()).days + 1
        if days < 1:
            days = 1

        # WORK rows
        if etype == "work":
            if wmode == "remote":
                # set rate based on domestic/foreign
                if rtype == "domestic":
                    df.at[idx, "Per_Diem_Rate"] = inland_rate
                elif rtype == "foreign":
                    df.at[idx, "Per_Diem_Rate"] = foreign_rate
                else:
                    df.at[idx, "Per_Diem_Rate"] = 0.0
                df.at[idx, "Per_Diem_Total"] = round(days * df.at[idx, "Per_Diem_Rate"], 2)
                df.at[idx, "Km_Rate"] = 0.0
                df.at[idx, "Distance_km"] = 0.0
                df.at[idx, "Travel_Cost"] = 0.0

                if not row["Description"].strip():
                    df.at[idx, "Description"] = f"Remote work ({rtype}) from {row['Start']} to {row['End']}"
            else:
                # Onsite or anything else → no per-diem
                df.at[idx, "Per_Diem_Rate"] = 0.0
                df.at[idx, "Per_Diem_Total"] = 0.0
                df.at[idx, "Km_Rate"] = 0.0
                df.at[idx, "Distance_km"] = 0.0
                df.at[idx, "Travel_Cost"] = 0.0

                if not row["Description"].strip():
                    df.at[idx, "Description"] = f"{wmode.title()} work from {row['Start']} to {row['End']}"
                df.at[idx, "Remote_Type"] = "n/a"

        # TRAVEL rows
        elif etype == "travel":
            dist = float(row["Distance_km"])
            if dist < 0:
                dist = 0.0
            df.at[idx, "Km_Rate"] = km_rate
            df.at[idx, "Travel_Cost"] = round(dist * km_rate, 2)
            df.at[idx, "Per_Diem_Rate"]  = 0.0
            df.at[idx, "Per_Diem_Total"] = 0.0

            if not row["Description"].strip():
                df.at[idx, "Description"] = f"Travel on {row['Start']} covering {dist} km"
            if wmode not in ["onsite", "remote"]:
                df.at[idx, "Work_Mode"] = "remote"
            if not rtype:
                df.at[idx, "Remote_Type"] = "n/a"

        # FREE days
        elif etype == "free":
            df.at[idx, "Work_Mode"]     = "free"
            df.at[idx, "Remote_Type"]   = "n/a"
            df.at[idx, "Per_Diem_Rate"]  = 0.0
            df.at[idx, "Per_Diem_Total"] = 0.0
            df.at[idx, "Km_Rate"]        = 0.0
            df.at[idx, "Distance_km"]    = 0.0
            df.at[idx, "Travel_Cost"]    = 0.0

            if not row["Description"].strip():
                df.at[idx, "Description"] = f"Free from {row['Start']} to {row['End']}"
        else:
            # anything else → mark as free placeholder
            df.at[idx, "Event_Type"]    = "free"
            df.at[idx, "Work_Mode"]     = "free"
            df.at[idx, "Remote_Type"]   = "n/a"
            df.at[idx, "Per_Diem_Rate"]  = 0.0
            df.at[idx, "Per_Diem_Total"] = 0.0
            df.at[idx, "Km_Rate"]        = 0.0
            df.at[idx, "Distance_km"]    = 0.0
            df.at[idx, "Travel_Cost"]    = 0.0
            df.at[idx, "Description"]    = f"Free from {row['Start']} to {row['End']}"

    return df


def build_initial_timeline(from_date: str, to_date: str) -> pd.DataFrame:
    """
    Create a DataFrame with one row per day in [from_date, to_date],
    each pre-filled as a "free" placeholder from 00:00 to 23:59.
    """
    start_date = datetime.strptime(from_date, DATE_ONLY_FORMAT)
    end_date   = datetime.strptime(to_date,   DATE_ONLY_FORMAT)

    rows = []
    cur = start_date
    while cur <= end_date:
        rows.append({
            "Start":  cur.strftime(DATETIME_FORMAT),
            "End":    (cur + timedelta(hours=23, minutes=59)).strftime(DATETIME_FORMAT),
            "Event_Type":   "free",
            "Work_Mode":    "free",
            "Remote_Type":  "n/a",
            "Per_Diem_Rate":  0.0,
            "Km_Rate":        0.0,
            "Distance_km":    0.0,
            "Per_Diem_Total": 0.0,
            "Travel_Cost":    0.0,
            "Description":    f"Free from {cur.strftime(DATETIME_FORMAT)} to {(cur + timedelta(hours=23, minutes=59)).strftime(DATETIME_FORMAT)}"
        })
        cur += timedelta(days=1)

    return pd.DataFrame(rows, columns=COLUMNS)

def load_or_init_dataframe(path: str, from_date: str, to_date: str) -> pd.DataFrame:
    """
    If CSV exists, load it; otherwise build an initial 'free placeholder' timeline.
    """
    if os.path.isfile(path):
        df = pd.read_csv(path, dtype=str)
        # Ensure missing columns exist
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = ""
        return df.reindex(columns=COLUMNS)
    else:
        return build_initial_timeline(from_date, to_date)


#
# 3) STREAMLIT UI LAYOUT
#
st.set_page_config(page_title="German Remote/Onsite Tax Allowance Manager", layout="wide")

st.title("📊 German Remote/Onsite Work Tax-Allowance GUI")

# Sidebar: basic parameters
with st.sidebar:
    st.header("Configuration")
    from_date = st.text_input("From Date (YYYY-MM-DD)", value="2025-06-01")
    to_date   = st.text_input("To Date   (YYYY-MM-DD)", value="2025-06-30")

    inland_rate  = st.number_input("Per-diem (domestic)", min_value=0.0, step=1.0, value=14.0)
    foreign_rate = st.number_input("Per-diem (foreign)",  min_value=0.0, step=1.0, value=28.0)
    km_rate      = st.number_input("Rate per km",          min_value=0.0, step=0.10, value=0.30)

    output_path  = st.text_input("Output CSV file", value="events_with_per_diem_and_travel.csv")
    do_recalc     = st.checkbox("Only recalculate existing CSV", value=False)

    st.markdown("---")
    st.caption("Press **Recalculate & Save** to write to CSV.\n\n"
               "Editing is instant (click on any cell).")

# Validate dates
try:
    _ = datetime.strptime(from_date, DATE_ONLY_FORMAT)
    _ = datetime.strptime(to_date,   DATE_ONLY_FORMAT)
except Exception:
    st.error("❌ Invalid `From Date` or `To Date`. Must be YYYY-MM-DD.")
    st.stop()

# Load or initialize the table
df = load_or_init_dataframe(output_path, from_date, to_date)

# If “recalculate only” is checked: immediately recalc fields and exit
if do_recalc:
    df = recalculate_dataframe(df, inland_rate, foreign_rate, km_rate)
    # sort by Start
    df["SortKey"] = df["Event_Type"].map({"work": 0, "free": 0, "travel": 1})
    df = df.sort_values(by=["Start", "SortKey"]).drop(columns=["SortKey"])
    df.to_csv(output_path, index=False)
    st.success(f"✅ Recalculated existing CSV → saved to `{output_path}`")
    st.dataframe(df.head(10))
    st.stop()

# Build AgGrid options to allow editing
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_default_column(editable=True, resizable=True)
gb.configure_column("Per_Diem_Rate", editable=False)
gb.configure_column("Per_Diem_Total", editable=False)
gb.configure_column("Travel_Cost", editable=False)
gb.configure_column("Km_Rate", editable=False)
gb.configure_column("Event_Type", cellEditor="agSelectCellEditor", cellEditorParams={"values": ["work", "travel", "free"]})
gb.configure_column("Work_Mode", cellEditor="agSelectCellEditor", cellEditorParams={"values": ["onsite", "remote", "free"]})
gb.configure_column("Remote_Type", cellEditor="agSelectCellEditor", cellEditorParams={"values": ["domestic", "foreign", "n/a"]})
grid_opts = gb.build()

st.write("## Editable Events Table (click any cell to edit)")
grid_response = AgGrid(
    df,
    gridOptions=grid_opts,
    update_mode=GridUpdateMode.VALUE_CHANGED,
    fit_columns_on_grid_load=True,
    enable_enterprise_modules=False,
    height=400,
    width="100%",
)

# Retrieve the edited dataframe
edited_df = pd.DataFrame(grid_response["data"])

# “Recalculate & Save” button
if st.button("🔄 Recalculate & Save"):
    final_df = recalculate_dataframe(edited_df.copy(), inland_rate, foreign_rate, km_rate)
    # sort by Start & Event_Type
    final_df["SortKey"] = final_df["Event_Type"].map({"work": 0, "free": 0, "travel": 1})
    final_df = final_df.sort_values(by=["Start", "SortKey"]).drop(columns=["SortKey"])
    final_df.to_csv(output_path, index=False)
    st.success(f"✅ Saved to `{output_path}`")
    st.dataframe(final_df.head(10))

#
# 4) FOOTER / NOTES
#
st.markdown("---")
st.caption(
    "• Use the grid above exactly like an Excel sheet: edit any cell in place.\n"
    "• Even if you delete some rows or insert new ones, pressing “Recalculate & Save” will fill in all derived columns.\n"
    "• If you want to start over, delete the CSV file on disk and reload this app.\n"
    "• To create initial placeholders, simply leave everything as “free” (the app will fill in default descriptions)."
)
