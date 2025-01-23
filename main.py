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
import json


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
            padding-right: 2.5px !important; /* Add space before the text */


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

    # Sort categories by total count
    unique_categories = crime_counts.sort_values(ascending=False).index.tolist()

    # Ensure consistent ordering by converting to categorical
    df["ReversedStatisticGroup"] = pd.Categorical(
        df["ReversedStatisticGroup"], categories=unique_categories, ordered=True
    )
    filtered_data["ReversedStatisticGroup"] = pd.Categorical(
        filtered_data["ReversedStatisticGroup"], categories=unique_categories, ordered=True
    )

    ticktext = [
        "\u202Bעבירות פליליות\nכלליות",
        "\u202Bעבירות מוסר\nוסדר ציבורי",
        "\u202Bעבירות\nביטחון",
        "\u202Bעבירות\nכלכליות ומנהליות",
        "\u202Bעבירות\nמרמה",
        "\u202Bעבירות\nתנועה"
    ]
    ticktext = [text[::-1] for text in ticktext]

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
            palette=["#FF5733", "#FFC300", "#28B463", "#1E90FF"],
            order=unique_categories,
            ax=ax,
            zorder=2
        )
        ax.set_title("גוסו ןועבר יפל םיעשפה רפסמ", fontsize=16)
        ax.set_xlabel("עשפה גוס", fontsize=14)
        ax.set_ylabel("תוריבעה תומכ", fontsize=14)
        ax.set_xticks(range(len(ticktext)))  # Ensure tick positions are correct
        ax.set_xticklabels(ticktext, rotation=0, ha='center', fontsize=12)  # Apply wrapped labels
        ax.grid(axis='y', color='lightgrey', linewidth=0.5, zorder=0)

    else:
        crime_counts = crime_counts.reindex(unique_categories, fill_value=0)  # Ensure same order
        crime_counts.index = ticktext  # Update index with wrapped labels
        crime_counts.plot(kind="bar", ax=ax, color='orange', zorder=2)

        ax.set_xticklabels(
            ax.get_xticklabels(),
            rotation=0,  # Keep labels horizontal
            ha='center',  # Center-align labels
            fontsize=12
        )
        ax.set_xlabel("עשפה גוס", fontsize=14)
        ax.set_ylabel("תוריבעה תומכ", fontsize=14)
        ax.set_ylim(0, 18000)
        ax.grid(axis='y', color='lightgrey', linewidth=0.5)



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
    df_all = pd.read_csv('clean_df_heatmap.csv')
    layer_name = "PoliceMerhavBoundaries"
    gdf = gpd.read_file(gdb_path, layer=layer_name)

    # Convert GeoDataFrame to GeoJSON and reproject to WGS84
    gdf = gdf.to_crs(epsg=4326)
    gdf['record_count'] = 0  # Initialize record count for mapping
    gdf['centroid_lat'] = gdf.geometry.centroid.y
    gdf['centroid_lon'] = gdf.geometry.centroid.x

    # Sort and prepare dropdown options
    sorted_crimes = ['כל סוגי העבירות'] + sorted(df_all['StatisticGroup'].unique())
    sorted_merhavim = ['כל המרחבים'] + sorted(gdf['MerhavName'].unique())
    years = ['לאורך כל השנים', 2020, 2021, 2022, 2023, 2024]
    gdf['unique_id'] = gdf.index

    st.markdown(
        """
        <style>
        /* Align dropdown menus to the right and reduce their width */
        .stSelectbox > div {
            direction: rtl; /* Make text right-to-left for Hebrew */
            text-align: right; /* Align text inside the dropdown */
            width: 200px; /* Reduce dropdown width */
            margin-left: auto; /* Push dropdown to the right */
            margin-right: 0; /* Remove extra margin */
        }

        /* Align titles and labels to the right */
        .stText {
            text-align: right; /* Align Streamlit text elements to the right */
            direction: rtl; /* Right-to-left direction for Hebrew */
        }
        /* Align all text elements (labels, titles) to the right */
        .stMarkdown, .stSelectbox label {
            text-align: right; /* Align text to the right */
            direction: rtl; /* Right-to-left direction for Hebrew */
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Streamlit layout
    st.title("מפת חום - עבירות משטרת ישראל")

    # Dropdowns for user selection
    selected_crime = st.selectbox("בחר סוג עבירה:", options=sorted_crimes)
    selected_year = st.selectbox("בחר שנה:", options=years)

    # Filter data based on selections
    if selected_crime == 'כל סוגי העבירות':
        filtered_df = df_all
    else:
        filtered_df = df_all[df_all['StatisticGroup'] == selected_crime]

    if selected_year != 'לאורך כל השנים':
        filtered_df = filtered_df[filtered_df['Year'] == int(selected_year)]

    # Summarize counts by Merhav
    merhav_counts = filtered_df['PoliceMerhav'].value_counts()
    gdf['record_count'] = gdf['MerhavName'].map(merhav_counts).fillna(0)

    fig = px.choropleth_mapbox(
        gdf,
        geojson=json.loads(gdf.to_json()),
        locations='unique_id',
        color="record_count",
        hover_name="MerhavName",
        hover_data={"record_count": True, 'unique_id': False},  # Exclude "unique_id" from tooltips
        mapbox_style="carto-positron",
        center={"lat": 31.5, "lon": 34.8},  # Centered on Israel
        zoom=6.3,  # Adjusted zoom level to fit Israel
        # color_continuous_scale="Pinkyl",
        title=f"{selected_year} מפת עבירות" if selected_year != 'לאורך כל השנים' else "2020-2024 מפת עבירות",
        labels={"record_count": "מספר עבירות"}
    )

    fig.update_traces(
        reversescale=True  # Set to True if you want to reverse light-to-dark order
    )

    # Update layout for vertical orientation
    fig.update_layout(
        mapbox=dict(
            center={"lat": 31.5, "lon": 34.8},  # Center on Israel
            zoom=6.2,  # Zoom out slightly to show entire Israel
            style="carto-positron"
        ),
        height=800,  # Taller map for vertical orientation
        width=500,
        title_x=0.4# Narrower map
    )
    # Display the map
    st.plotly_chart(fig, use_container_width=True)