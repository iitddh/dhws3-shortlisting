import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1bhK-_vyRhcubcl-bey1VuiggYoV1K9PBLfrVhGtvyCE"
RANGE_RESPONSES = "Form Responses 1!A:ZZ"
RANGE_LOCATION = "location_mapping!A:ZZ"
SHEET_RESPONSES_TITLE = "Form Responses 1"

CATEGORY_COL = "15. Are you applying as a"
DEGREE_COL = "7. Last degree attained"
NAME_COL = "1. Full name"

@st.cache_resource
def build_client():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["service_account"],
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)

@st.cache_resource
def load_data():
    client = build_client()

    resp = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_RESPONSES,
    ).execute()
    rows = resp.get("values", [])

    if not rows:
        df = pd.DataFrame()
    else:
        header = rows[0]
        n_cols = len(header)
        data_rows = []
        for r in rows[1:]:
            if len(r) < n_cols:
                r = r + [""] * (n_cols - len(r))
            elif len(r) > n_cols:
                r = r[:n_cols]
            data_rows.append(r)
        df = pd.DataFrame(data_rows, columns=header)

    loc = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_LOCATION,
    ).execute()
    loc_rows = loc.get("values", [])
    if not loc_rows:
        df_location = pd.DataFrame()
    else:
        loc_header = loc_rows[0]
        n_loc_cols = len(loc_header)
        loc_data = []
        for r in loc_rows[1:]:
            if len(r) < n_loc_cols:
                r = r + [""] * (n_loc_cols - len(r))
            elif len(r) > n_loc_cols:
                r = r[:n_loc_cols]
            loc_data.append(r)
        df_location = pd.DataFrame(loc_data, columns=loc_header)

    return df, df_location

def save_marks_and_remarks(row_index_0based, marks, remarks):
    client = build_client()
    df, _ = load_data()

    cols = list(df.columns)
    marks_col_idx = cols.index("Marks")
    remarks_col_idx = cols.index("Remarks")

    full_row = df.iloc[row_index_0based].tolist()
    full_row[marks_col_idx] = str(marks)
    full_row[remarks_col_idx] = str(remarks)

    sheet_row = row_index_0based + 2
    range_name = f"{SHEET_RESPONSES_TITLE}!{sheet_row}:{sheet_row}"

    body = {"values": [full_row]}
    client.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueInputOption="RAW",
        body=body,
    ).execute()

df, df_location = load_data()

st.title("DHWS3 Shortlisting App")

# Ensure required columns exist
for col in ["Application ID", "Marks", "Remarks"]:
    if col not in df.columns:
        st.error(f"Column '{col}' not found in 'Form Responses 1'. Please add it.")
        st.stop()

for col in [CATEGORY_COL, DEGREE_COL, NAME_COL]:
    if col not in df.columns:
        st.error(f"Column '{col}' not found. Check header name.")
        st.stop()

# Generate Application IDs if empty
app_id_col = df["Application ID"].astype(str).str.strip()
if app_id_col.isna().all() or (app_id_col == "").all():
    df["Application ID"] = ["C" + str(i).zfill(3) for i in range(1, len(df) + 1)]

# Sidebar filters
st.sidebar.title("Filters")

# Category filter
categories = ["All"] + sorted(df[CATEGORY_COL].dropna().unique().tolist())
selected_cat = st.sidebar.selectbox("Category", categories, key="cat")

# Last degree filter
degrees = ["All"] + sorted(df[DEGREE_COL].dropna().unique().tolist())
selected_degree = st.sidebar.selectbox("Last degree attained", degrees, key="deg")

# Text search (name, email, any field)
search_text = st.sidebar.text_input("Search (name, email, etc.)", value="", key="search")

# Marks filter - only applied if user changes from defaults
marks_min = st.sidebar.number_input("Min marks", min_value=0, max_value=10, value=0, key="mmin")
marks_max = st.sidebar.number_input("Max marks", min_value=0, max_value=10, value=10, key="mmax")
apply_marks_filter = (marks_min != 0) or (marks_max != 10)

df_filtered = df.copy()

# Category
if selected_cat != "All":
    df_filtered = df_filtered[df_filtered[CATEGORY_COL] == selected_cat]

# Degree
if selected_degree != "All":
    df_filtered = df_filtered[df_filtered[DEGREE_COL] == selected_degree]

# Text search across all columns
if search_text.strip():
    q = search_text.lower()
    mask = df_filtered.apply(
        lambda row: any(q in str(v).lower() for v in row.values),
        axis=1
    )
    df_filtered = df_filtered[mask]

# Marks filter (only if user changed defaults)
if apply_marks_filter:
    marks_numeric = pd.to_numeric(df_filtered["Marks"], errors="coerce")
    df_filtered = df_filtered[(marks_numeric >= marks_min) & (marks_numeric <= marks_max)]

df_filtered = df_filtered.reset_index(drop=True)

st.write(f"Showing {len(df_filtered)} of {len(df)} applications")

if df_filtered.empty:
    st.warning("No applications match the selected filters.")
    st.stop()

# Select application
app_options = df_filtered["Application ID"].tolist()
selected_app = st.selectbox("Select application", app_options)

# Find row in original df
row_in_df = int(df[df["Application ID"] == selected_app].index[0])
row_display = df.iloc[row_in_df]

st.subheader(f"Application {selected_app}")

# Show all fields in a readable way
st.write("### Details")
for col in df.columns:
    if col in ["Application ID", "Marks", "Remarks"]:
        continue
    st.write(f"**{col}**: {row_display[col]}")

# Review section
st.write("### Review")
current_marks = row_display["Marks"]
current_remarks = row_display["Remarks"]

try:
    marks_init = int(float(current_marks)) if pd.notna(current_marks) and current_marks not in ["", None] else 0
except Exception:
    marks_init = 0

remarks_init = str(current_remarks) if pd.notna(current_remarks) and current_remarks not in ["", None] else ""

marks_input = st.number_input("Marks (out of 10)", min_value=0, max_value=10, value=marks_init)
remarks_input = st.text_area("Remarks", value=remarks_init)

if st.button("Save marks and remarks"):
    save_marks_and_remarks(row_in_df, marks_input, remarks_input)
    st.success("Saved! Reloading...")
    st.rerun()
