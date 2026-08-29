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
    df = pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()

    loc = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_LOCATION,
    ).execute()
    loc_rows = loc.get("values", [])
    df_location = pd.DataFrame(loc_rows[1:], columns=loc_rows[0]) if loc_rows else pd.DataFrame()

    return df, df_location

def save_marks_and_remarks(row_index_0based, marks, remarks):
    client = build_client()
    df, _ = load_data()

    cols = list(df.columns)
    marks_col_idx = cols.index("Marks")
    remarks_col_idx = cols.index("Remarks")

    # Build full row
    full_row = df.iloc[row_index_0based].tolist()
    full_row[marks_col_idx] = str(marks)
    full_row[remarks_col_idx] = str(remarks)

    # Sheet row number: header is row 1, data starts at row 2
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

if CATEGORY_COL not in df.columns:
    st.error(f"Column '{CATEGORY_COL}' not found. Check header name.")
    st.stop()

# Generate Application IDs if empty
if df["Application ID"].isna().all() or (df["Application ID"].astype(str).str.strip() == "").all():
    df["Application ID"] = ["C" + str(i).zfill(3) for i in range(1, len(df) + 1)]

# Sidebar filters
st.sidebar.title("Filters")
categories = ["All"] + sorted(df[CATEGORY_COL].dropna().unique().tolist())
selected_cat = st.sidebar.selectbox("Category", categories)

if selected_cat != "All":
    df_filtered = df[df[CATEGORY_COL] == selected_cat].reset_index(drop=True)
else:
    df_filtered = df.reset_index(drop=True)

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
