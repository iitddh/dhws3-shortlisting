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
STATE_COL = "4. State / Union Territory of travel origin"
DISCIPLINE_COL = "9. Graduation discipline / area of study"
HS_LANG_COL = "14. Which languages were used as the medium of instruction in your high school? Select all that apply."

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

for col in [CATEGORY_COL, DEGREE_COL, NAME_COL, STATE_COL, DISCIPLINE_COL]:
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

df_filtered = df_filtered.reset_index(drop=True)

st.write(f"Showing {len(df_filtered)} of {len(df)} applications")

# Visualizations
st.header("Overview")

if not df_filtered.empty:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("State / UT distribution")
        if STATE_COL in df_filtered.columns:
            state_counts = df_filtered[STATE_COL].value_counts().reset_index()
            state_counts.columns = ["State / UT", "Count"]
            st.bar_chart(state_counts.set_index("State / UT"))

    with col2:
        st.subheader("Last degree attained")
        if DEGREE_COL in df_filtered.columns:
            degree_counts = df_filtered[DEGREE_COL].value_counts().reset_index()
            degree_counts.columns = ["Degree", "Count"]
            st.bar_chart(degree_counts.set_index("Degree"))

    st.subheader("Discipline
