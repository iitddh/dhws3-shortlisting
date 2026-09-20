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
COURSE_LEVEL_COL = "16. Which course / programme level are you currently pursuing?"
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


@st.cache_data(ttl=30)
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

        for row in rows[1:]:
            row = list(row)
            if len(row) < n_cols:
                row.extend([""] * (n_cols - len(row)))
            elif len(row) > n_cols:
                row = row[:n_cols]
            data_rows.append(row)

        df = pd.DataFrame(data_rows, columns=header)

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

        for row in loc_rows[1:]:
            row = list(row)
            if len(row) < n_loc_cols:
                row.extend([""] * (n_loc_cols - len(row)))
            elif len(row) > n_loc_cols:
                row = row[:n_loc_cols]
            loc_data.append(row)

        df_location = pd.DataFrame(loc_data, columns=loc_header)

    return df, df_location


def column_letter(index_0based):
    result = ""
    index = index_0based + 1

    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result

    return result


def backfill_application_ids(df):
    client = build_client()
    header = list(df.columns)
    app_id_col_idx = header.index("Application ID")

    data = []

    for i, row in df.iterrows():
        current_id = "" if pd.isna(row["Application ID"]) else str(row["Application ID"]).strip()

        if not current_id:
            expected_id = "C" + str(i + 1).zfill(3)
            app_id_col = column_letter(app_id_col_idx)
            sheet_row = i + 2

            data.append(
                {
                    "range": f"{SHEET_RESPONSES_TITLE}!{app_id_col}{sheet_row}",
                    "values": [[expected_id]],
                }
            )

    if not data:
        return

    body = {
        "valueInputOption": "RAW",
        "data": data,
    }

    client.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body=body,
    ).execute()

    load_data.clear()


def save_marks_and_remarks(orig_idx_0based, marks, remarks):
    client = build_client()
    df, _ = load_data()

    cols = list(df.columns)
    marks_col_idx = cols.index("Marks")
    remarks_col_idx = cols.index("Remarks")

    marks_col = column_letter(marks_col_idx)
    remarks_col = column_letter(remarks_col_idx)
    sheet_row = orig_idx_0based + 2

    body = {
        "valueInputOption": "RAW",
        "data": [
            {
                "range": f"{SHEET_RESPONSES_TITLE}!{marks_col}{sheet_row}",
                "values": [[str(marks)]],
            },
            {
                "range": f"{SHEET_RESPONSES_TITLE}!{remarks_col}{sheet_row}",
                "values": [[str(remarks)]],
            },
        ],
    }

    client.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body=body,
    ).execute()

    load_data.clear()


def normalize_marks(series):
    marks_text = (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )

    marks_numeric = pd.to_numeric(
        marks_text.replace("", pd.NA),
        errors="coerce",
    )

    is_marked = marks_text.ne("") & marks_numeric.notna()

    return marks_text, marks_numeric, is_marked


# Load data
df, df_location = load_data()

st.title("DHWS3 Shortlisting App")

# Ensure required columns exist
for col in ["Application ID", "Marks", "Remarks"]:
    if col not in df.columns:
        st.error(
            f"Column '{col}' not found in 'Form Responses 1'. "
            "Please add it."
        )
        st.stop()

for col in [
    CATEGORY_COL,
    DEGREE_COL,
    COURSE_LEVEL_COL,
    NAME_COL,
    STATE_COL,
    DISCIPLINE_COL,
]:
    if col not in df.columns:
        st.error(f"Column '{col}' not found. Check the exact header name.")
        st.stop()

# Backfill blank application IDs in the spreadsheet
app_id_text = (
    df["Application ID"]
    .fillna("")
    .astype(str)
    .str.strip()
)

if app_id_text.eq("").any():
    backfill_application_ids(df)
    df, df_location = load_data()

# Generate in-memory IDs only as a safety fallback
df["Application ID"] = (
    df["Application ID"]
    .fillna("")
    .astype(str)
    .str.strip()
)

for i in range(len(df)):
    if df.at[i, "Application ID"] == "":
        df.at[i, "Application ID"] = "C" + str(i + 1).zfill(3)

# Sidebar filters
st.sidebar.title("Filters")

categories = ["All"] + sorted(
    df[CATEGORY_COL].dropna().astype(str).unique().tolist()
)
selected_cat = st.sidebar.selectbox(
    "Category",
    categories,
    key="cat",
)

degrees = ["All"] + sorted(
    df[DEGREE_COL].dropna().astype(str).unique().tolist()
)
selected_degree = st.sidebar.selectbox(
    "Last degree attained",
    degrees,
    key="deg",
)

course_levels = ["All"] + sorted(
    df[COURSE_LEVEL_COL].dropna().astype(str).unique().tolist()
)
selected_course_level = st.sidebar.selectbox(
    "Course / programme level",
    course_levels,
    key="course",
)

search_text = st.sidebar.text_input(
    "Search (name, email, etc.)",
    value="",
    key="search",
)

review_status = st.sidebar.selectbox(
    "Review status",
    ["All", "Marked", "Unmarked"],
    key="review_status",
)

score_filter = st.sidebar.selectbox(
    "Score filter",
    [
        "All scores",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "0–4",
        "5–6",
        "7–8",
        "9–10",
    ],
    key="score_filter",
)

# Apply filters
df_filtered = df.copy()

if selected_cat != "All":
    df_filtered = df_filtered[
        df_filtered[CATEGORY_COL] == selected_cat
    ]

if selected_degree != "All":
    df_filtered = df_filtered[
        df_filtered[DEGREE_COL] == selected_degree
    ]

if selected_course_level != "All":
    df_filtered = df_filtered[
        df_filtered[COURSE_LEVEL_COL] == selected_course_level
    ]

if search_text.strip():
    q = search_text.lower()

    mask = df_filtered.apply(
        lambda row: any(
            q in str(value).lower()
            for value in row.values
        ),
        axis=1,
    )

    df_filtered = df_filtered[mask]

marks_text, marks_numeric, is_marked = normalize_marks(
    df_filtered["Marks"]
)

if review_status == "Marked":
    df_filtered = df_filtered[is_marked]

elif review_status == "Unmarked":
    df_filtered = df_filtered[~is_marked]

if score_filter != "All scores":
    if score_filter in {
        "0", "1", "2", "3", "4",
        "5", "6", "7", "8", "9", "10",
    }:
        selected_score = int(score_filter)
        score_mask = is_marked & marks_numeric.eq(selected_score)

    else:
        score_ranges = {
            "0–4": (0, 4),
            "5–6": (5, 6),
            "7–8": (7, 8),
            "9–10": (9, 10),
        }

        minimum, maximum = score_ranges[score_filter]
        score_mask = (
            is_marked
            & marks_numeric.between(minimum, maximum)
        )

    df_filtered = df_filtered[score_mask]

df_filtered = df_filtered.reset_index(drop=True)

st.write(
    f"Showing {len(df_filtered)} of {len(df)} applications"
)

# Visualizations
st.header("Overview")

if not df_filtered.empty:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("State / UT distribution")
        state_counts = (
            df_filtered[STATE_COL]
            .value_counts()
            .reset_index()
        )
        state_counts.columns = ["State / UT", "Count"]
        st.bar_chart(state_counts.set_index("State / UT"))

    with col2:
        st.subheader("Last degree attained")
        degree_counts = (
            df_filtered[DEGREE_COL]
            .value_counts()
            .reset_index()
        )
        degree_counts.columns = ["Degree", "Count"]
        st.bar_chart(degree_counts.set_index("Degree"))

    st.subheader("Discipline")
    discipline_counts = (
        df_filtered[DISCIPLINE_COL]
        .value_counts()
        .reset_index()
    )
    discipline_counts.columns = ["Discipline", "Count"]
    st.bar_chart(discipline_counts.set_index("Discipline"))

    st.subheader("High school medium of instruction")
    lang_counts = {}

    for value in df_filtered[HS_LANG_COL].dropna():
        for language in str(value).split(","):
            language = language.strip()
            if language:
                lang_counts[language] = (
                    lang_counts.get(language, 0) + 1
                )

    if lang_counts:
        lang_df = pd.DataFrame(
            list(lang_counts.items()),
            columns=["Language", "Count"],
        ).sort_values("Count", ascending=False)
        st.bar_chart(lang_df.set_index("Language"))

if df_filtered.empty:
    st.info("No applications match the selected filters.")
    st.stop()

# Reset navigation when filters change
filter_signature = (
    selected_cat,
    selected_degree,
    selected_course_level,
    search_text,
    review_status,
    score_filter,
)

if (
    "filter_signature" not in st.session_state
    or st.session_state.filter_signature != filter_signature
):
    st.session_state.idx = 0
    st.session_state.filter_signature = filter_signature

if "idx" not in st.session_state:
    st.session_state.idx = 0

if st.session_state.idx >= len(df_filtered):
    st.session_state.idx = max(0, len(df_filtered) - 1)

# Top navigation
col_prev, col_next = st.columns(2)

with col_prev:
    if st.button(
        "← Previous",
        disabled=(st.session_state.idx == 0),
    ):
        st.session_state.idx -= 1
        st.rerun()

with col_next:
    if st.button(
        "Next →",
        disabled=(st.session_state.idx == len(df_filtered) - 1),
    ):
        st.session_state.idx += 1
        st.rerun()

current_row = df_filtered.iloc[st.session_state.idx]
selected_app = current_row["Application ID"]
orig_idx = int(current_row["_orig_idx"])

st.subheader(
    f"Application {selected_app} "
    f"({st.session_state.idx + 1} / {len(df_filtered)})"
)

# Details
st.write("### Details")

for col in df.columns:
    if col in ["Application ID", "Marks", "Remarks", "_orig_idx"]:
        continue
    st.write(f"**{col}**: {current_row[col]}")

# Review
st.write("### Review")

current_marks = current_row["Marks"]
current_remarks = current_row["Remarks"]

current_marks_text = (
    ""
    if pd.isna(current_marks)
    else str(current_marks).strip()
)

if current_marks_text == "":
    marks_init = 0
    st.caption("Status: Unmarked")
else:
    try:
        marks_init = int(float(current_marks_text))
        st.caption(f"Status: Marked — {current_marks_text}/10")
    except (TypeError, ValueError):
        marks_init = 0
        st.caption("Status: Unmarked")

remarks_init = (
    ""
    if pd.isna(current_remarks)
    else str(current_remarks)
)

marks_input = st.number_input(
    "Marks (out of 10)",
    min_value=0,
    max_value=10,
    value=marks_init,
    step=1,
)

remarks_input = st.text_area(
    "Remarks",
    value=remarks_init,
)

if st.button("Save marks and remarks"):
    save_marks_and_remarks(
        orig_idx,
        marks_input,
        remarks_input,
    )
    st.success("Saved! Reloading...")
    st.rerun()

# Bottom navigation
st.divider()
col_prev2, col_next2 = st.columns(2)

with col_prev2:
    if st.button(
        "← Previous",
        key="prev2",
        disabled=(st.session_state.idx == 0),
    ):
        st.session_state.idx -= 1
        st.rerun()

with col_next2:
    if st.button(
        "Next →",
        key="next2",
        disabled=(st.session_state.idx == len(df_filtered) - 1),
    ):
        st.session_state.idx += 1
        st.rerun()
