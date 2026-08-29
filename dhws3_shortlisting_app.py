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

    # Store original 0-based row index (data rows start at row 2 in sheet)
    df["_orig_idx"] = list(range(len(df)))

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

def save_marks_and_remarks(orig_idx_0based, marks, remarks):
    client = build_client()
    df, _ = load_data()

    cols = list(df.columns)
    marks_col_idx = cols.index("Marks")
    remarks_col_idx = cols.index("Remarks")

    row = df[df["_orig_idx"] == orig_idx_0based].iloc[0].tolist()
    row[marks_col_idx] = str(marks)
    row[remarks_col_idx] = str(remarks)

    # Sheet row number: header is row 1, data starts at row 2
    sheet_row = orig_idx_0based + 2
    range_name = f"{SHEET_RESPONSES_TITLE}!{sheet_row}:{sheet_row}"

    body = {"values": [row]}
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

    st.subheader("Discipline")
    if DISCIPLINE_COL in df_filtered.columns:
        discipline_counts = df_filtered[DISCIPLINE_COL].value_counts().reset_index()
        discipline_counts.columns = ["Discipline", "Count"]
        st.bar_chart(discipline_counts.set_index("Discipline"))

    st.subheader("High school medium of instruction")
    if HS_LANG_COL in df_filtered.columns:
        lang_counts = {}
        for val in df_filtered[HS_LANG_COL].dropna():
            for lang in str(val).split(","):
                lang = lang.strip()
                if lang:
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if lang_counts:
            lang_df = pd.DataFrame(list(lang_counts.items()), columns=["Language", "Count"])
            lang_df = lang_df.sort_values("Count", ascending=False)
            st.bar_chart(lang_df.set_index("Language"))

if df_filtered.empty:
    st.warning("No applications match the selected filters.")
    st.stop()

# Navigation state
if "idx" not in st.session_state or st.session_state.get("_last_len") != len(df_filtered):
    st.session_state.idx = 0
    st.session_state._last_len = len(df_filtered)

# Prev / Next buttons (top)
col_prev, col_next = st.columns(2)
with col_prev:
    if st.button("← Previous", disabled=(st.session_state.idx == 0)):
        st.session_state.idx -= 1
        st.rerun()
with col_next:
    if st.button("Next →", disabled=(st.session_state.idx == len(df_filtered) - 1)):
        st.session_state.idx += 1
        st.rerun()

current_row = df_filtered.iloc[st.session_state.idx]
selected_app = current_row["Application ID"]
orig_idx = int(current_row["_orig_idx"])

st.subheader(f"Application {selected_app} ({st.session_state.idx + 1} / {len(df_filtered)})")

# Show all fields in a readable way
st.write("### Details")
for col in df.columns:
    if col in ["Application ID", "Marks", "Remarks", "_orig_idx"]:
        continue
    st.write(f"**{col}**: {current_row[col]}")

# Review section
st.write("### Review")
current_marks = current_row["Marks"]
current_remarks = current_row["Remarks"]

try:
    marks_init = int(float(current_marks)) if pd.notna(current_marks) and current_marks not in ["", None] else 0
except Exception:
    marks_init = 0

remarks_init = str(current_remarks) if pd.notna(current_remarks) and current_remarks not in ["", None] else ""

marks_input = st.number_input("Marks (out of 10)", min_value=0, max_value=10, value=marks_init)
remarks_input = st.text_area("Remarks", value=remarks_init)

if st.button("Save marks and remarks"):
    save_marks_and_remarks(orig_idx, marks_input, remarks_input)
    st.success("Saved! Reloading...")
    st.rerun()

# Prev / Next buttons (bottom)
st.divider()
col_prev2, col_next2 = st.columns(2)
with col_prev2:
    if st.button("← Previous", key="prev2", disabled=(st.session_state.idx == 0)):
        st.session_state.idx -= 1
        st.rerun()
with col_next2:
    if st.button("Next →", key="next2", disabled=(st.session_state.idx == len(df_filtered) - 1)):
        st.session_state.idx += 1
        st.rerun()
