import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
import html
import re

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

st.set_page_config(
    page_title="DHWS3 Shortlisting App",
    layout="wide",
)

st.markdown(
    """
    <style>
    .question-label {
        background-color: #eaf2ff;
        border-left: 5px solid #2f6fed;
        color: #174a9c;
        font-weight: 700;
        padding: 0.55rem 0.75rem;
        margin-top: 0.9rem;
        margin-bottom: 0.15rem;
        border-radius: 4px;
        line-height: 1.35;
    }

    .applicant-response {
        background-color: #fff8e6;
        border-left: 5px solid #e0a000;
        color: #222222;
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.7rem;
        border-radius: 4px;
        white-space: normal;
        line-height: 1.45;
        overflow-wrap: anywhere;
    }

    .applicant-response a {
        color: #0757a5;
        text-decoration: underline;
        font-weight: 600;
    }

    .legend-box {
        background-color: #f7f7f7;
        border: 1px solid #dddddd;
        border-radius: 5px;
        padding: 0.6rem 0.8rem;
        margin-bottom: 1rem;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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

    response = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_RESPONSES,
    ).execute()

    rows = response.get("values", [])

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

    location_response = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_LOCATION,
    ).execute()

    location_rows = location_response.get("values", [])

    if not location_rows:
        df_location = pd.DataFrame()
    else:
        location_header = location_rows[0]
        n_location_cols = len(location_header)
        location_data = []

        for row in location_rows[1:]:
            row = list(row)

            if len(row) < n_location_cols:
                row.extend([""] * (n_location_cols - len(row)))
            elif len(row) > n_location_cols:
                row = row[:n_location_cols]

            location_data.append(row)

        df_location = pd.DataFrame(
            location_data,
            columns=location_header,
        )

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
    app_id_col = column_letter(app_id_col_idx)

    data = []

    for i, row in df.iterrows():
        current_id = (
            ""
            if pd.isna(row["Application ID"])
            else str(row["Application ID"]).strip()
        )

        if not current_id:
            expected_id = "C" + str(i + 1).zfill(3)
            sheet_row = i + 2

            data.append(
                {
                    "range": (
                        f"{SHEET_RESPONSES_TITLE}!"
                        f"{app_id_col}{sheet_row}"
                    ),
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

    columns = list(df.columns)

    marks_col_idx = columns.index("Marks")
    remarks_col_idx = columns.index("Remarks")

    marks_col = column_letter(marks_col_idx)
    remarks_col = column_letter(remarks_col_idx)
    sheet_row = orig_idx_0based + 2

    body = {
        "valueInputOption": "RAW",
        "data": [
            {
                "range": (
                    f"{SHEET_RESPONSES_TITLE}!"
                    f"{marks_col}{sheet_row}"
                ),
                "values": [[str(marks)]],
            },
            {
                "range": (
                    f"{SHEET_RESPONSES_TITLE}!"
                    f"{remarks_col}{sheet_row}"
                ),
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

    is_marked = (
        marks_text.ne("")
        & marks_numeric.notna()
    )

    return marks_text, marks_numeric, is_marked


def make_clickable_response(response):
    if pd.isna(response) or str(response).strip() == "":
        return "[No response provided]"

    response_text = str(response)
    escaped_text = html.escape(response_text, quote=True)
    url_pattern = r"https?://[^\s<]+"

    def replace_url(match):
        matched_url = match.group(0)
        trailing_punctuation = ""

        while matched_url and matched_url[-1] in ".,;:!?)]}":
            trailing_punctuation = (
                matched_url[-1] + trailing_punctuation
            )
            matched_url = matched_url[:-1]

        safe_url = html.escape(matched_url, quote=True)

        link = (
            f'<a href="{safe_url}" target="_blank" '
            f'rel="noopener noreferrer">{safe_url}</a>'
        )

        return link + trailing_punctuation

    clickable_text = re.sub(
        url_pattern,
        replace_url,
        escaped_text,
    )

    return clickable_text.replace("\n", "<br>")


def display_question_response(question, response):
    question_text = html.escape(str(question), quote=True)
    response_html = make_clickable_response(response)

    st.markdown(
        f"""
        <div class="question-label">
            {question_text}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="applicant-response">
            {response_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


df, df_location = load_data()

st.title("DHWS3 Shortlisting App")

for required_column in ["Application ID", "Marks", "Remarks"]:
    if required_column not in df.columns:
        st.error(
            f"Column '{required_column}' was not found in "
            "'Form Responses 1'. Please add it."
        )
        st.stop()

for required_column in [
    CATEGORY_COL,
    DEGREE_COL,
    COURSE_LEVEL_COL,
    NAME_COL,
    STATE_COL,
    DISCIPLINE_COL,
]:
    if required_column not in df.columns:
        st.error(
            f"Column '{required_column}' was not found. "
            "Check the exact header name."
        )
        st.stop()


app_id_text = (
    df["Application ID"]
    .fillna("")
    .astype(str)
    .str.strip()
)

if app_id_text.eq("").any():
    backfill_application_ids(df)
    df, df_location = load_data()


df["Application ID"] = (
    df["Application ID"]
    .fillna("")
    .astype(str)
    .str.strip()
)

for i in range(len(df)):
    if df.at[i, "Application ID"] == "":
        df.at[i, "Application ID"] = "C" + str(i + 1).zfill(3)


st.sidebar.title("Filters")

categories = ["All"] + sorted(
    df[CATEGORY_COL]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_cat = st.sidebar.selectbox(
    "Category",
    categories,
    key="cat",
)


degrees = ["All"] + sorted(
    df[DEGREE_COL]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_degree = st.sidebar.selectbox(
    "Last degree attained",
    degrees,
    key="deg",
)


course_levels = ["All"] + sorted(
    df[COURSE_LEVEL_COL]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
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


score_range = st.sidebar.slider(
    "Score range",
    min_value=0,
    max_value=10,
    value=(0, 10),
    step=1,
    key="score_range",
)


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
    query = search_text.lower()

    search_mask = df_filtered.apply(
        lambda row: any(
            query in str(value).lower()
            for value in row.values
        ),
        axis=1,
    )

    df_filtered = df_filtered[search_mask]


marks_text, marks_numeric, is_marked = normalize_marks(
    df_filtered["Marks"]
)

if review_status == "Marked":
    df_filtered = df_filtered[is_marked]

elif review_status == "Unmarked":
    df_filtered = df_filtered[~is_marked]


minimum_score, maximum_score = score_range

if score_range != (0, 10):
    score_mask = (
        is_marked
        & marks_numeric.between(
            minimum_score,
            maximum_score,
        )
    )

    df_filtered = df_filtered[score_mask]


df_filtered = df_filtered.reset_index(drop=True)

st.write(
    f"Showing {len(df_filtered)} of {len(df)} applications"
)


st.header("Overview")

if not df_filtered.empty:
    st.subheader("State / UT distribution")

    state_counts = (
        df_filtered[STATE_COL]
        .value_counts()
        .reset_index()
    )

    state_counts.columns = ["State / UT", "Count"]

    st.bar_chart(
        state_counts.set_index("State / UT")
    )

    st.subheader("Last degree attained")

    degree_counts = (
        df_filtered[DEGREE_COL]
        .value_counts()
        .reset_index()
    )

    degree_counts.columns = ["Degree", "Count"]

    st.bar_chart(
        degree_counts.set_index("Degree")
    )

    st.subheader("Discipline")

    discipline_counts = (
        df_filtered[DISCIPLINE_COL]
        .value_counts()
        .reset_index()
    )

    discipline_counts.columns = ["Discipline", "Count"]

    st.bar_chart(
        discipline_counts.set_index("Discipline")
    )

    st.subheader("High school medium of instruction")

    language_counts = {}

    for value in df_filtered[HS_LANG_COL].dropna():
        for language in str(value).split(","):
            language = language.strip()

            if language:
                language_counts[language] = (
                    language_counts.get(language, 0) + 1
                )

    if language_counts:
        language_df = pd.DataFrame(
            list(language_counts.items()),
            columns=["Language", "Count"],
        ).sort_values(
            "Count",
            ascending=False,
        )

        st.bar_chart(
            language_df.set_index("Language")
        )

    st.subheader("Score distribution")

    score_values = pd.to_numeric(
        df_filtered["Marks"],
        errors="coerce",
    ).dropna()

    if score_values.empty:
        st.info(
            "No marked applications are available for the score chart."
        )
    else:
        score_counts = (
            score_values
            .astype(int)
            .value_counts()
            .reindex(range(0, 11), fill_value=0)
            .sort_index()
        )

        score_chart_df = pd.DataFrame(
            {
                "Score": score_counts.index,
                "Applications": score_counts.values,
            }
        ).set_index("Score")

        st.bar_chart(
            score_chart_df,
            y="Applications",
        )


if df_filtered.empty:
    st.info("No applications match the selected filters.")
    st.stop()


filter_signature = (
    selected_cat,
    selected_degree,
    selected_course_level,
    search_text,
    review_status,
    score_range,
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
    st.session_state.idx = max(
        0,
        len(df_filtered) - 1,
    )


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
        disabled=(
            st.session_state.idx
            == len(df_filtered) - 1
        ),
    ):
        st.session_state.idx += 1
        st.rerun()


current_row = df_filtered.iloc[st.session_state.idx]
selected_app = current_row["Application ID"]
orig_idx = int(current_row["_orig_idx"])

st.subheader(
    f"Application {selected_app} "
    f"({st.session_state.idx + 1} / "
    f"{len(df_filtered)})"
)


st.markdown(
    """
    <div class="legend-box">
        <span style="color:#174a9c;font-weight:700;">
            Blue = form question
        </span>
        &nbsp; | &nbsp;
        <span style="color:#9a6a00;font-weight:700;">
            Yellow = applicant response
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)


st.write("### Application details")

for column in df.columns:
    if column in [
        "Application ID",
        "Marks",
        "Remarks",
        "_orig_idx",
    ]:
        continue

    display_question_response(
        column,
        current_row[column],
    )


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
        st.caption(
            f"Status: Marked — "
            f"{current_marks_text}/10"
        )
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
        disabled=(
            st.session_state.idx
            == len(df_filtered) - 1
        ),
    ):
        st.session_state.idx += 1
        st.rerun()
