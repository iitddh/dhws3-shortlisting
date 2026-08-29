import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
import os

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1bhK-_vyRhcubcl-bey1VuiggYoV1K9PBLfrVhGtvyCE"  # <-- replace with your Sheet ID
RANGE_RESPONSES = "Form Responses 1!A:ZZ"
RANGE_LOCATION = "location_mapping!A:ZZ"

@st.cache_resource
def load_sheets():
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=SCOPES,
    )
    client = build("sheets", "v4", credentials=creds)

    resp = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_RESPONSES,
    ).execute()
    rows = resp.get("values", [])
    df_responses = pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()

    loc = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_LOCATION,
    ).execute()
    loc_rows = loc.get("values", [])
    df_location = pd.DataFrame(loc_rows[1:], columns=loc_rows[0]) if loc_rows else pd.DataFrame()

    return df_responses, df_location

df_responses, df_location = load_sheets()

st.title("DHWS3 Shortlisting App")

st.write("Responses shape:", df_responses.shape)
st.write("Location shape:", df_location.shape)

st.dataframe(df_responses)
st.dataframe(df_location)