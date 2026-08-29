import streamlit as st

st.title("Secrets test")

try:
    sa = st.secrets["service_account"]
    st.write("Keys in service_account:", list(sa.keys()))
    st.write("client_email:", sa.get("client_email"))
    st.write("project_id:", sa.get("project_id"))
    st.write("private_key starts with:", sa.get("private_key", "")[:30])
except Exception as e:
    st.error(f"Error reading secrets: {e}")
