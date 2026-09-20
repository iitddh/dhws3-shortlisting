def column_letter(index_0based):
    result = ""
    index = index_0based + 1

    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result

    return result


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

    # Force the next rerun to read the latest spreadsheet values
    load_data.clear()
