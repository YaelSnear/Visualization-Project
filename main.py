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
    .stCheckbox label {
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
    years = ["All Years (mean)"] + sorted(df["Year"].dropna().unique().astype(int).tolist())
    # Sidebar filters
    year_selected = st.selectbox(":בחר שנה", years, index=0)
    st.markdown("""
        <style>
        .stSelectbox [data-baseweb="select"] {
            width: 200px !important;
            text-align: right;
            direction: rtl;
        }
        .stCheckbox label {
            text-align: right;  /* Align checkbox label to the right */
            direction: rtl;
        }
        .plotly-title {
            text-align: right !important;  /* Align plotly title to the right */
        }
        </style>
    """, unsafe_allow_html=True)
    split_by_quarter = st.checkbox("Split by Quarter")

    # Filter data based on selected year
    unique_categories = df["ReversedStatisticGroup"].drop_duplicates().tolist()
    if year_selected == "All Years (mean)":
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
    df = load_data()
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
        lambda row: row["Count"] / quarters_before if row["Period"] == "לפני ה7.10" else row["Count"] / quarters_after,
        axis=1
    )

    districts = sorted(
        grouped["PoliceDistrict"].unique(),
        key=lambda x: (x != "כל המחוזות", x)
    )

    # Title
    st.title("השוואת פשיעה לפי סוגי עבירות ומחוזות")

    # Dropdown for selecting district
    selected_district = st.selectbox(
        "בחר מחוז:",
        districts,
        index=0  # Default to "כל המחוזות"
    )

    # Filter data based on selected district
    if selected_district == "כל המחוזות":
        filtered_df = grouped
    else:
        filtered_df = grouped[grouped["PoliceDistrict"] == selected_district]

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
    elif selected_district in districts:
        y_tick_interval = 100
        y_max = 1000
    else:
        y_tick_interval = 100
        y_max = 1000  # Default for other districts

    # Generate bar chart
    fig = px.bar(
        pivot_df,
        x="Category",
        y=["לפני ה7.10", "אחרי ה7.10"],
        barmode="group",
        labels={"value": "כמות עבירות מנורמלת", "variable": "תקופה"},
        title=f"פשיעה במחוז: {selected_district}"
    ).update_layout(
        xaxis_title="סוגי עבירות",
        yaxis_title="כמות עבירות מנורמלת",
        legend_title="תקופה",
        plot_bgcolor="#f9f9f9",
        yaxis=dict(
            tickmode="linear",
            tick0=0,
            dtick=y_tick_interval,  # Set tick interval based on district
            range=[0, y_max]  # Set upper limit based on district
        )
    )

    # Display bar chart
    st.plotly_chart(fig)

elif menu_option == 'Heatmap':

    gdb_path = extract_zip()
    df = pd.read_csv('clean_df_heatmap.csv')
    layer_name = "PoliceMerhavBoundaries"
    gdf = gpd.read_file(gdb_path, layer=layer_name)

    sorted_crimes = sorted(df['StatisticGroup'].dropna().unique(), key=lambda x: x) # sort crimes in alphabetical order
    sorted_crimes = ['all_crimes'] + sorted_crimes

    # visualization
    # Title
    st.title("מפת חום - עבירות משטרת ישראל")

    # Dropdown for crime type
    selected_crime = st.selectbox(
        "בחר סוג עבירה:",
        options=sorted_crimes,
        index=0  # Default to 'all crimes'
    )

    # Dropdown for year
    selected_year = st.selectbox(
        "בחר שנה:",
        options=['לאורך כל השנים', 2020, 2021, 2022, 2023, 2024],
        index=0  # Default to 'all years'
    )

    # Filter data based on user selection
    if selected_crime == 'all_crimes':
        # Group and sum all crimes by PoliceMerhav
        merhav_counts = df.groupby('PoliceMerhav').size()
    else:
        filtered_df = df[df['StatisticGroup'] == selected_crime]
        merhav_counts = filtered_df['PoliceMerhav'].value_counts()

    # Map the counts to the GeoDataFrame
    gdf['record_count'] = gdf['MerhavName'].map(merhav_counts).fillna(0)

    # Generate the heatmap
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    gdf.plot(
        column='record_count',
        ax=ax,
        legend=True,
        legend_kwds={'label': "Number of Records by Police Merhav", 'orientation': "horizontal"},
        cmap='YlOrRd',
        edgecolor='black'
    )
    ax.set_title(
        f"Heatmap of {selected_crime} for {selected_year}" if selected_year != 'לאורך כל השנים' else f"Heatmap of {selected_crime} (All Years)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    # Display the heatmap in Streamlit
    st.pyplot(fig)