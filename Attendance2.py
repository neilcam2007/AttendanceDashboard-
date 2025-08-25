import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth

# ------------------------------
# Page config
# ------------------------------
st.set_page_config(page_title="Attendance Dashboard", layout="wide")

# ------------------------------
# Authentication setup
# ------------------------------
names = ["Jurgen"]
usernames = ["jurgen"]
passwords = ["Director_Office"]

# Hash passwords
hashed_passwords = stauth.Hasher(passwords).generate()

credentials = {
    "usernames": {
        usernames[0]: {
            "name": names[0],
            "password": hashed_passwords[0]
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    "app_home",  # cookie name
    "abcdef",    # key for cookie
    30           # cookie expiry days
)

# ------------------------------
# Login
# ------------------------------
name, authentication_status, username = authenticator.login(location="main")

# ------------------------------
# Access control
# ------------------------------
if authentication_status:

    st.success(f"Welcome {name}!")
    authenticator.logout("Logout", "main")  # optional logout button
    st.info("Remeber to log out when you are done using the application.")
    # ------------------------------
    # Status Mapping
    # ------------------------------
    status_mapping = {
        "P": "Present", "VL": "Vacation Leave", "SL": "Sick Leave",
        "BV": "Bereavement Leave", "MT": "Maternity Leave", "ML": "Marriage Leave",
        "BL": "Birth Leave", "PL": "Parental Leave", "AD": "Adoption Leave",
        "JL": "Jury Leave", "PRL": "Pre-retirement Leave", "SD": "Study Leave",
        "SPL": "Special Paid Leave", "UL": "Unpaid Leave", "A": "Absent",
        "TO": "Time Off", "OD": "Off Day", "C": "Injury",
        "I": "Interdicted", "DP": "Detained Leave", "S": "Suspended"
    }

    # ------------------------------
    # Helper Functions
    # ------------------------------
    def get_section_from_row4(file):
        df_preview = pd.read_excel(file, sheet_name=0, header=None)
        if df_preview.shape[0] >= 4:
            row4 = df_preview.iloc[3]
            for idx, cell in enumerate(row4):
                if pd.notna(cell) and str(cell).strip().lower() == "section":
                    for next_cell in row4[idx + 1:]:
                        if pd.notna(next_cell) and str(next_cell).strip():
                            return str(next_cell).strip()
        return None

    def detect_header_row(file):
        preview = pd.read_excel(file, sheet_name=0, header=None, nrows=20)
        for idx, row in preview.iterrows():
            row_str = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if "surname" in row_str or "name" in row_str:
                return idx
        return 0

    def drop_numbering_column(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        name_matches = [c for c in df.columns if str(c).strip().lower() in {"no.","no","#","nr","num","number"}]
        if name_matches:
            return df.drop(columns=name_matches[0])
        first_col = df.columns[0]
        s = df[first_col]
        try:
            nums = pd.to_numeric(s, errors="coerce").dropna()
            if len(nums) >= max(3, int(0.6*len(s))):
                if (nums.astype(int) == nums).all() and nums.is_monotonic_increasing:
                    if int(nums.iloc[0]) in (0,1) and int(nums.iloc[-1]) <= len(s)+2:
                        return df.drop(columns=[first_col])
        except Exception:
            pass
        return df

    def load_attendance(file):
        section_name = get_section_from_row4(file)
        header_row = detect_header_row(file)
        df = pd.read_excel(file, sheet_name=0, header=header_row)
        df.columns = [str(col).strip().replace("*","") for col in df.columns]
        df = drop_numbering_column(df)
        keep_cols = ["Surname & Name","Status","Site of Work","REMARKS","FROM","TO","TOTAL"]
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]
        rename_dict = {
            "Surname & Name":"Name & Surname",
            "Status":"Status",
            "Site of Work":"Site of Work",
            "REMARKS":"Remarks",
            "FROM":"Leave From",
            "TO":"Leave To",
            "TOTAL":"Leave Total"
        }
        df = df.rename(columns={k:v for k,v in rename_dict.items() if k in df.columns})
        if "Name & Surname" in df.columns:
            df = df.dropna(subset=["Name & Surname"], how="all")
        if "Status" in df.columns:
            df["Status_Full"] = df["Status"].apply(lambda x: status_mapping.get(str(x).strip(), str(x).strip()))
        else:
            df["Status_Full"] = ""
        return section_name, df

    # ------------------------------
    # File Upload and Display
    # ------------------------------
    uploaded_files = st.file_uploader(
        "Upload one or more attendance Excel files",
        type=["xlsx","xls"],
        accept_multiple_files=True
    )

    if uploaded_files:
        for file_idx, file in enumerate(uploaded_files):
            section_name, df = load_attendance(file)
            if "Name & Surname" not in df.columns or "Status" not in df.columns:
                st.warning("File does not contain necessary columns. Skipping this file.")
                continue

            # Sidebar filters
            st.sidebar.markdown(f"### Filters for {section_name or 'Unknown Section'}")
            names = df["Name & Surname"].dropna().unique()
            selected_name = st.sidebar.selectbox(
                "Filter by Name & Surname", ["All"] + list(names), key=f"name_{file_idx}"
            )
            if selected_name != "All":
                df = df[df["Name & Surname"] == selected_name]

            if "Site of Work" in df.columns:
                sites = df["Site of Work"].dropna().unique()
                selected_site = st.sidebar.selectbox(
                    "Filter by Site of Work", ["All"] + list(sites), key=f"site_{file_idx}"
                )
                if selected_site != "All":
                    df = df[df["Site of Work"] == selected_site]

            statuses = df["Status"].dropna().unique()
            selected_status = st.sidebar.selectbox(
                "Filter by Status", ["All"] + list(statuses), key=f"status_{file_idx}"
            )
            if selected_status != "All":
                df = df[df["Status"] == selected_status]

            # Section title
            st.markdown(f"### {section_name or 'Unknown Section'}")

            # Highlight Name & Surname based on Status
            def highlight_name(row):
                status = str(row["Status_Full"]).strip()
                if status == "Present":
                    return ["color: green; font-weight: bold;" if col=="Name & Surname" else "" for col in row.index]
                elif status == "Absent":
                    return ["color: red; font-weight: bold;" if col=="Name & Surname" else "" for col in row.index]
                else:
                    return ["color: orange; font-weight: bold;" if col=="Name & Surname" else "" for col in row.index]

            styled = df.style.apply(highlight_name, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)

            # Dynamic Summary
            st.markdown("<h5> Attendance Summary </h5>", unsafe_allow_html=True)
            status_counts = df["Status_Full"].value_counts()
            if len(status_counts) > 0:
                cols = st.columns(len(status_counts))
                for i,(status,count) in enumerate(status_counts.items()):
                    cols[i].metric(status, count)

            st.markdown("---")

else:
    st.info("Please log in to access the attendance dashboard.")