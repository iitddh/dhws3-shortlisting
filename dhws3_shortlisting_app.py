import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1bhK-_vyRhcubcl-bey1VuiggYoV1K9PBLfrVhGtvyCE"  # <-- replace with your real Sheet ID
RANGE_RESPONSES = "Form Responses 1!A:ZZ"
RANGE_LOCATION = "location_mapping!A:ZZ"

st.title("DHWS3 Shortlisting App (debug)")

try:
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["service_account"],
        scopes=SCOPES,
    )
    client = build("sheets", "v4", credentials=creds)

    resp = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_RESPONSES,
    ).execute()
    rows = resp.get("values", [])
    import pandas as pd
    df_responses = pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()

    loc = client.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_LOCATION,
    ).execute()
    loc_rows = loc.get("values", [])
    df_location = pd.DataFrame(loc_rows[1:], columns=loc_rows[0]) if loc_rows else pd.DataFrame()

    st.write("Responses shape:", df_responses.shape)
    st.write("Location shape:", df_location.shape)
    st.dataframe(df_responses)
    st.dataframe(df_location)

except HttpError as e:
    st.error("HttpError occurred:")
    st.write("Status:", e.resp.status)
    st.write("Reason:", e.reason if hasattr(e, "reason") else "unknown")
    st.write("Content:", str(e.content))
except Exception as e:
    st.error(f"Other error: {e}")
