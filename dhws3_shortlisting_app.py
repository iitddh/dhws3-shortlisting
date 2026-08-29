import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1bhK-_vyRhcubcl-bey1VuiggYoV1K9PBLfrVhGtvyCE"  # <-- replace with your real Sheet ID
RANGE_RESPONSES = "Form Responses 1!A:ZZ"
RANGE_LOCATION = "location_mapping!A:ZZ"

SHEET_RESPONSES_TITLE = "Form Responses 1"

@st.cache_resource
def build_client():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["service_account"],
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)

@st.cache_resource
def load_sheets():
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

def save_marks_and_remarks(row_index_1based, marks, remarks):
    client = build_client()
    # Columns: Application ID, Marks, Remarks are the last 3 columns we added.
    # We'll write to columns by header name to be safe.
    body = {
        "values": [[str(marks), str(remarks)]]
    }
    # Find column letters for Marks and Remarks
    df, _ = load_sheets()
    cols = list(df.columns)
    marks_col = cols.index("Marks") + 1
    remarks_col = cols.index("Remarks") + 1
    start_col = marks_col
    end_col = remarks_col

    range_name = f"{SHEET_RESPONSES_TITLE}!{row_index_1based + 1}:{row_index_1based + 1}"
    # We'll write only Marks and Remarks; Application ID is computed separately.
    # For simplicity, write Marks at column marks_col, Remarks at remarks_col.
    marks_range = f"{SHEET_RESPONSES_TITLE}!{row_index_1based + 1}:{row_index_1based + 1}"
    # Build
