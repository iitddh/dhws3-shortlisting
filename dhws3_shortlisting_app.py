import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from location_utils import match_location_to_mapping

SHEET_ID = "YOUR_SHEET_ID"  # <-- replace with your Google Sheet ID
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_data
def load_sheets():
    creds = Credentials.from_service_account_info(st.secrets["service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    
    responses_sheet = spreadsheet.get_worksheet_by_index(0)
    df_responses = pd.DataFrame(responses_sheet.get_all_records())
    
    location_sheet = spreadsheet.worksheet("location_mapping")
    df_location = pd.DataFrame(location_sheet.get_all_records())
    
    return df_responses, df_location

def save_scores(df_responses):
    creds = Credentials.from_service_account_info(st.secrets["service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    responses_sheet = spreadsheet.get_worksheet_by_index(0)
    
    responses_sheet.clear()
    responses_sheet.update([df_responses.columns.tolist()] + df_responses.values.tolist())

st.set_page_config(page_title="DHWS3 Shortlisting", layout="wide")
st.title("DHWS3 Shortlisting Dashboard")

df_responses, df_location = load_sheets()

# Derive metro_nonmetro
df_responses["metro_nonmetro"] = df_responses.apply(
    lambda row: match_location_to_mapping(
        row.get("City / town / district you would be traveling from", ""),
        row.get("State / Union Territory", ""),
        df_location
    ),
    axis=1
)

st.sidebar.header("Filters")
metro_filter = st.sidebar.multiselect("Metro/Non-Metro", options=df_responses["metro_nonmetro"].unique(), default=df_responses["metro_nonmetro"].unique())
state_filter = st.sidebar.multiselect("State/UT", options=df_responses["State / Union Territory"].unique(), default=df_responses["State / Union Territory"].unique())

filtered_df = df_responses[
    df_responses["metro_nonmetro"].isin(metro_filter) &
    df_responses["State / Union Territory"].isin(state_filter)
]

st.header("Overview")
col1, col2, col3 = st.columns(3)
col1.metric("Total", len(filtered_df))
col2.metric("Metro", len(filtered_df[filtered_df["metro_nonmetro"]=="metro"]))
col3.metric("Non-Metro", len(filtered_df[filtered_df["metro_nonmetro"]=="nonmetro"]))

st.subheader("Discipline")
st.bar_chart(filtered_df["Graduation discipline / area of study"].value_counts())

st.subheader("State")
st.bar_chart(filtered_df["State / Union Territory"].value_counts())

st.header("Scoring")

if "Score" not in df_responses.columns:
    df_responses["Score"] = None
if "Remarks" not in df_responses.columns:
    df_responses["Remarks"] = None
if "Shortlist_status" not in df_responses.columns:
    df_responses["Shortlist_status"] = None

for idx, row in filtered_df.iterrows():
    with st.expander(f"{row.get('Full name', 'Unknown')}"):
        st.write(f"City: {row.get('City / town / district you would be traveling from')}")
        st.write(f"State: {row.get('State / Union Territory')}")
        st.write(f"Metro/Non-Metro: {row.get('metro_nonmetro')}")
        st.write(f"Discipline: {row.get('Graduation discipline / area of study')}")
        
        score = st.number_input("Score (0-10)", min_value=0, max_value=10, value=int(row["Score"]) if pd.notnull(row["Score"]) else 0, key=f"s{idx}")
        remarks = st.text_input("Remarks", value=str(row["Remarks"]) if pd.notnull(row["Remarks"]) else "", key=f"r{idx}")
        status = st.selectbox("Status", ["Shortlisted", "Waitlist", "Reject", ""], value=str(row["Shortlist_status"]) if pd.notnull(row["Shortlist_status"]) else "", key=f"t{idx}")
        
        df_responses.at[idx, "Score"] = score
        df_responses.at[idx, "Remarks"] = remarks
        df_responses.at[idx, "Shortlist_status"] = status

if st.button("Save to Sheet"):
    save_scores(df_responses)
    st.success("Saved!")
