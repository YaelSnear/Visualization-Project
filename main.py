import zipfile
import plotly.express as px
import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
import io
import geopandas as gpd
from io import BytesIO
import base64
import fiona
import mplcursors
from shapely.geometry import Point


#set page config
st.set_page_config(page_title="Crime Dashboard", layout="wide")

# Helper functions
@st.cache_data
def load_data():
    urls = {
        "2020": "https://data.gov.il/api/3/action/datastore_search?resource_id=520597e3-6003-4247-9634-0ae85434b971",
        "2021": "https://data.gov.il/api/3/action/datastore_search?resource_id=3f71fd16-25b8-4cfe-8661-e6199db3eb12",
        "2022": "https://data.gov.il/api/3/action/datastore_search?resource_id=a59f3e9e-a7fe-4375-97d0-76cea68382c1",
        "2023": "https://data.gov.il/api/3/action/datastore_search?resource_id=32aacfc9-3524-4fba-a282-3af052380244",
        "2024": "https://data.gov.il/api/3/action/datastore_search?resource_id=5fc13c50-b6f3-4712-b831-a75e0f91a17e",
    }
    data_frames = []
    for year, url in urls.items():
        response = requests.get(url)
        data = response.json()
        records = data['result']['records']
        df = pd.DataFrame(records)
        df['Year'] = int(year)  # Add year column
        df["Category"] = df["StatisticGroup"].apply(categorize_statistic_group)
        df = df.dropna(subset=["Category"])
        df["ReversedStatisticGroup"] = df["Category"].apply(lambda x: x[::-1])
        data_frames.append(df)
    return pd.concat(data_frames, ignore_index=True)

def categorize_statistic_group(stat_group):
    """
    Divides the statistic groups into 6
    :param stat_group: the initial statistic group
    :return: one of the 6 groups it belongs to
    """
    categories = {
        "עבירות פליליות כלליות": ['עבירות כלפי הרכוש', 'עבירות נגד גוף', 'עבירות נגד אדם', 'עבירות מין'],
        "עבירות מוסר וסדר ציבורי": ['עבירות כלפי המוסר', 'עבירות סדר ציבורי'],
        "עבירות ביטחון": ['עבירות בטחון'],
        "עבירות כלכליות ומנהליות": ['עבירות כלכליות', 'עבירות מנהליות', 'עבירות רשוי'],
        "עבירות תנועה": ['עבירות תנועה'],
        "עבירות מרמה": ['עבירות מרמה']
    }
    for category, types in categories.items():
        if stat_group in types:
            return category
    return None

def preprocess_data_district(df):
    """
    preprocessed the districts names
    :param df: out data frame
    :return: pandas df with the district names preprocessed
    """
    # remove nan values
    filtered_df = df[~df["PoliceDistrict"].isin(["כל הארץ", ""])]

    # make a joined district
    aggregated_df = filtered_df.groupby(["Category", "Period"]).agg({"Count": "sum"}).reset_index()
    aggregated_df["PoliceDistrict"] = "כל המחוזות"
    combined_df = pd.concat([filtered_df, aggregated_df], ignore_index=True)

    return combined_df

def extract_zip():
    # נתיב לקובץ ה-ZIP שהועלה
    zip_path = "policestationboundaries.gdb.zip"

    # חלץ את התוכן לתוך קולאב
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("PoliceStationBoundaries")

    # ודא שהתיקייה קיימת
    gdb_path = "PoliceStationBoundaries/PoliceStationBoundaries.gdb"
    return gdb_path

st.markdown("""
    <style>
    .block-container {
        text-align: right;  /* יישור כל האלמנטים לימין */
    }
    div[data-baseweb="select"] > div {
        direction: rtl;  /* שינוי כיוון ל-RTL */
        text-align: right; /* יישור לימין */
    }
    .stCheckbox {
        direction: rtl;  /* שינוי כיוון ל-RTL */
        text-align: right; /* יישור לימין */
    }
    </style>
""", unsafe_allow_html=True)
# Streamlit layout
st.title("פשיעה בארץ ישראל")

# side-bar navigation
menu_option = st.sidebar.radio("Select Visualization:", ["Overview", "Heatmap", "October 7th"])

if menu_option == 'Overview':
    df = load_data()
    # OVERVIEW VISUALIZATION
    # Determine Y-axis max value before filtering
    years = ["כל השנים (ממוצע)"] + sorted(df["Year"].dropna().unique().astype(int).tolist())
    st.markdown("""
        <style>
        /* Align the selectbox text and menu to the right */
        div[data-testid="stSelectbox"] * {
            text-align: right !important; /* Align all text inside the dropdown */
            direction: rtl !important;   /* Force right-to-left text direction */
        }

        /* Set a shorter width for the selectbox */
        div[data-testid="stSelectbox"] > div {
            width: 200px; 
        }

        /* Align the dropdown to the right */
        div[data-testid="stSelectbox"] {
            text-align: right;
            direction: rtl;
        }

        /* Align checkbox text */
        div[data-testid="stCheckbox"] * {
            text-align: right !important;
            direction: rtl !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Sidebar filters
    year_selected = st.selectbox("בחר שנה:", years, index=0)
    split_by_quarter = st.checkbox("חלוקה לרבעונים")

    # Filter data based on selected year
    unique_categories = df["ReversedStatisticGroup"].drop_duplicates().tolist()
    if year_selected == "כל השנים (ממוצע)":
        filtered_data = df
        crime_counts = (
            filtered_data.groupby("ReversedStatisticGroup").size() / len(filtered_data["Year"].unique())
        ).reindex(unique_categories, fill_value=0)
    else:
        filtered_data = df[df["Year"] == int(year_selected)]
        crime_counts = filtered_data["ReversedStatisticGroup"].value_counts().reindex(unique_categories, fill_value=0)

    # Generate plot
    fig, ax = plt.subplots(figsize=(10, 6))
    if split_by_quarter:
        if year_selected == "All Years (mean)":
            # Calculate mean for all years grouped by category and quarter
            grouped_data = (
                filtered_data.groupby(["ReversedStatisticGroup", "Quarter", "Year"])  # Include "Year" to count per year
                .size()
                .reset_index(name="Counts")  # Reset index to include 'Quarter' and 'Year'
                .groupby(["ReversedStatisticGroup", "Quarter"])[
                    "Counts"]  # Group by 'ReversedStatisticGroup' and 'Quarter'
                .mean()  # Calculate the mean across years
                .reset_index()  # Reset index to keep 'ReversedStatisticGroup' and 'Quarter'
            )

        else:
            # Group data for the selected year
            grouped_data = (
                filtered_data.groupby(["ReversedStatisticGroup", "Quarter"])
                .size()
                .reset_index(name="Counts")
            )
        sns.barplot(
            data=grouped_data,
            x="ReversedStatisticGroup",
            y="Counts",
            hue="Quarter",
            palette=['#9CFFFA', '#6153CC', '#FFED65', '#F96E46'],
            ax=ax
        )
        ax.set_title("גוסו ןועבר יפל םיעשפה רפסמ", fontsize=16)
        ax.set_xlabel("עשפה גוס", fontsize=14)
        ax.set_ylabel("ןועבר", fontsize=14)
    else:
        crime_counts.plot(kind="bar", ax=ax, color="#F96E46")
        ax.set_title("גוס יפל םיעשפה רפסמ", fontsize=16)
        ax.set_xlabel("עשפה גוס", fontsize=14)
        ax.set_ylabel("םיעשפה רפסמ", fontsize=14)
        ax.tick_params(axis="x", labelrotation=45)
        ax.set_ylim(0, 18000)

    plt.tight_layout()

    # Display plot
    st.pyplot(fig)

elif menu_option == 'October 7th':
    # Load and process data
    df = load_data()  # Ensure this function is defined and loads the correct dataset
    df["Quarter"] = df["Quarter"].str.extract(r"(\d)").astype(float)
    df["Period"] = "לפני ה7.10"
    df.loc[(df["Year"] == 2023) & (df["Quarter"] > 3), "Period"] = "אחרי ה7.10"
    df.loc[df["Year"] == 2024, "Period"] = "אחרי ה7.10"

    # Categorize statistic groups
    df["Category"] = df["StatisticGroup"].apply(categorize_statistic_group)

    # Drop rows where Category is None (uncategorized values)
    df = df.dropna(subset=["Category"])

    # Group by necessary fields
    grouped = df.groupby(["Category", "Period", "PoliceDistrict"]).size().reset_index(name="Count")

    # Apply preprocessing
    grouped = preprocess_data_district(grouped)

    # Normalize by quarter count
    quarters_before = (2023 - 2020) * 4 + 3  # First quarter of 2020 to third quarter of 2023
    quarters_after = 5  # Fourth quarter of 2023 to fourth quarter of 2024

    grouped["NormalizedCount"] = grouped.apply(
        lambda row: round(row["Count"] / quarters_before) if row["Period"] == "לפני ה7.10"
        else round(row["Count"] / quarters_after),
        axis=1
    )

    # Define districts
    districts = sorted(
        grouped["PoliceDistrict"].unique(),
        key=lambda x: (x != "כל המחוזות", x)
    )

    # Title
    st.markdown(
        '<h1 style="text-align: right; font-size: 36px; direction: rtl;">התפלגות עבירות לפני ואחרי ה-7.10</h1>',
        unsafe_allow_html=True
    )

    # Label and Dropdown styling
    st.markdown("""
        <style>
        /* Set the selectbox width */
        div[data-testid="stSelectbox"] > div {
            width: 200px;
        }

        /* Align the selectbox to the right */
        div[data-testid="stSelectbox"] {
            text-align: right;
            direction: rtl;
            margin-right: 10%;
            margin-top: -15px; /* Adjust space between label and dropdown */
        }

        /* Align dropdown items (listbox) to the right */
        div[role="listbox"] {
            text-align: right !important;
            direction: rtl !important;
        }

        /* Additional alignment for labels */
        label {
            text-align: right !important;
            direction: rtl;
            margin-right: 10%;
        }
        </style>
    """, unsafe_allow_html=True)

    # Label for the dropdown
    st.markdown("""
        <style>
        /* Align the label and dropdown to the right */
        div[data-testid="stSelectbox"] > label {
            text-align: right !important;
            direction: rtl !important;
            display: block;
            margin-right: 10%; /* Add margin to align properly */
            margin-bottom: 5px; /* Space between label and dropdown */
        }

        /* Align the dropdown box itself */
        div[data-testid="stSelectbox"] > div {
            text-align: right !important;
            direction: rtl !important;
            margin-right: 10%;
        }
        </style>
        <div style="text-align: right; direction: rtl; margin-right: 10%; font-size: 18px;">
            בחר מחוז:
        </div>
    """, unsafe_allow_html=True)

    selected_district = st.selectbox(
        "",
        districts,
        index=0,  # Default to "כל המחוזות"
        key="district-selector"
    )

    # Filter data based on selected district
    if selected_district == "כל המחוזות":
        filtered_df = grouped
    else:
        filtered_df = grouped[grouped["PoliceDistrict"] == selected_district]

    # Aggregate data
    aggregated_df = filtered_df.groupby(["Category", "Period"], as_index=False)["NormalizedCount"].sum()

    # Pivot the aggregated data
    pivot_df = (
        aggregated_df.pivot(index="Category", columns="Period", values="NormalizedCount")
        .fillna(0)  # Fill missing values with 0
        .reset_index()
    )

    # Adjust Y-axis based on selected district
    if selected_district == "כל המחוזות":
        y_tick_interval = 500
        y_max = 4000
    else:
        y_tick_interval = 100
        y_max = 1000

    # Generate bar chart
    pivot_df = pivot_df.sort_values(by=["לפני ה7.10", "אחרי ה7.10"], ascending=False)

    fig = px.bar(
        pivot_df,
        x="Category",
        y=["לפני ה7.10", "אחרי ה7.10"],
        barmode="group",
        labels={"value": "כמות עבירות מנורמלת לרבעון", "variable": "", "Category": "קטגוריה"},  # הורדת המילה "תקופה"
        title=f"פשיעה ב{selected_district}"  # Update title to "פשיעה ב"
    ).update_layout(
        xaxis_title="סוגי עבירות",
        yaxis_title="כמות עבירות מנורמלת לרבעון",
        legend_title="",  # הסרת כותרת האגדה
        plot_bgcolor="#f9f9f9",
        title=dict(
            text=f"פשיעה ב{selected_district}",  # Update title to "פשיעה ב"
            x=1,  # Align title to the right
            xanchor="right",  # Anchor title to the right
            font=dict(size=28)  # Adjust title font size
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=pivot_df["Category"].tolist(),
            ticktext=[
                "עבירות פליליות<br>כלליות",
                "עבירות מוסר<br>וסדר ציבורי",
                "עבירות<br>ביטחון",
                "עבירות<br>כלכליות ומנהליות",
                "עבירות<br>מרמה",
                "עבירות<br>תנועה"
            ],
            tickfont=dict(size=18),  # גודל הטקסט של הקטגוריות בציר X
            title_font=dict(size=20)  # גודל הטקסט של כותרת ציר X
        ),
        yaxis=dict(
            tickfont=dict(size=18),  # גודל הטקסט של המספרים בציר Y
            title_font=dict(size=20),  # גודל הטקסט של כותרת ציר Y
            gridcolor="lightgrey",  # צבע קווים חלש יותר
            gridwidth=0.5  # עובי קווים דק יותר
        ),
        legend=dict(
            font=dict(size=18)  # גודל הטקסט של האגדה (legend)
        ),
        height=700  # Increase height for better visualization
    )

    # Display bar chart
    st.plotly_chart(fig, use_container_width=True)
