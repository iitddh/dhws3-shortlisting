{\rtf1\ansi\ansicpg1252\cocoartf2870
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 def match_location_to_mapping(city, state, df_location):\
    city = str(city).strip()\
    state = str(state).strip()\
    \
    # Strategy 1: Exact match "State - City"\
    location_str = f"\{state\} - \{city\}"\
    match = df_location[df_location["location"] == location_str]\
    if not match.empty:\
        return match.iloc[0]["locationsType"]\
    \
    # Strategy 2: Try matching just the city part\
    partial_matches = df_location[df_location["location"].str.contains(city, case=False, na=False)]\
    if not partial_matches.empty:\
        if "metro" in partial_matches["locationsType"].values:\
            return "metro"\
        else:\
            return partial_matches.iloc[0]["locationsType"]\
    \
    # Strategy 3: Check for "Outside India"\
    if "outside" in city.lower() or "outside" in state.lower():\
        outside_matches = df_location[df_location["location"].str.contains("outside", case=False, na=False)]\
        if not outside_matches.empty:\
            return outside_matches.iloc[0]["locationsType"]\
    \
    # Default\
    return "nonmetro"}