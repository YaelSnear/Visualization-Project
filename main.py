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

def display_crime_categories():
    st.markdown("""
    <div style="text-align: right; direction: rtl; font-size: 18px; line-height: 1.6;">
    ### חלוקת עבירות לקבוצות
    במסגרת הניתוח, חילקנו את העבירות לקבוצות הבאות:
    - **עבירות פליליות כלליות**: עבירות כלפי הרכוש, עבירות נגד גוף, עבירות נגד אדם, עבירות מין.
    - **עבירות מוסר וסדר ציבורי**: עבירות כלפי המוסר, עבירות סדר ציבורי.
    - **עבירות ביטחון**: עבירות ביטחון.
    - **עבירות כלכליות ומנהליות**: עבירות כלכליות, עבירות מנהליות, עבירות רשוי.
    - **עבירות תנועה**: עבירות תנועה.
    - **עבירות מרמה**: עבירות מרמה.
    </div>
    """, unsafe_allow_html=True)


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
st.title("פשיעה במדינת ישראל בשנים 2020-2024")

st.markdown(
    """
    <style>
    /* Reverse the layout to move the sidebar to the right */
    .css-1d391kg {  /* Main container */
        flex-direction: row-reverse; /* Reverse the order of sidebar and main content */
    }
    .css-1y4p8pa { /* Sidebar container */
        text-align: right;  /* Align sidebar content to the right */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Sidebar with radio buttons
st.sidebar.title("בחרו שאלת מחקר:")
menu_option = st.sidebar.radio(
    "",
    [
        "התפלגות הפשיעה בישראל לאורך השנים",
        "התפלגות סוגי עבירות לפי מרחבים משטרתיים",
        "השפעות מאורעות ה-7.10.2023 על התפלגות הפשיעה בישראל"
    ]
)

# Inject custom CSS to align the sidebar content
st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        direction: rtl;
        text-align: right;
    }

    div[data-testid="stRadio"] > label {
        direction: rtl;
        text-align: right;
        margin-right: 10px;
    }

    div[data-testid="stRadio"] > div {
        text-align: right;
        direction: rtl;
    }
    </style>
    """, unsafe_allow_html=True)


if menu_option == 'התפלגות הפשיעה בישראל לאורך השנים':
    st.markdown("""
    <div style="text-align: right; direction: rtl; font-size: 18px; line-height: 1.6;">
    ברוכים הבאים לדף לניתוח ויזואלי של נתוני הפשיעה במדינת ישראל בין השנים 2020–2024. 
    דף זה נועד להציג תובנות ומגמות מתוך נתוני הפשיעה, תוך חלוקה לסוגי עבירות, מחוזות גיאוגרפיים והשפעתם של אירועים מרכזיים.

    באמצעות כלי ניתוח אינטראקטיביים, תוכלו לבחון את ההתפלגויות השונות, להשוות בין תקופות זמן ולגלות תובנות חדשות על השינויים שחלו לאורך השנים. 
    אנו מזמינים אתכם להשתמש בממשק זה לחקירה מעמיקה של נתוני הפשיעה בישראל ולקבלת תמונה רחבה ומדויקת יותר על הנושא.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align: right; direction: rtl; font-size: 18px; line-height: 1.8;">
    <h3>חלוקת עבירות לקבוצות</h3>
    במסגרת הניתוח, חילקנו את העבירות לקבוצות הבאות:
    <ul>
        <li><strong>עבירות פליליות כלליות:</strong> עבירות כלפי הרכוש, עבירות נגד גוף, עבירות נגד אדם, עבירות מין.</li>
        <li><strong>עבירות מוסר וסדר ציבורי:</strong> עבירות כלפי המוסר, עבירות סדר ציבורי.</li>
        <li><strong>עבירות ביטחון:</strong> עבירות ביטחון.</li>
        <li><strong>עבירות כלכליות ומנהליות:</strong> עבירות כלכליות, עבירות מנהליות, עבירות רשוי.</li>
        <li><strong>עבירות תנועה:</strong> עבירות תנועה.</li>
        <li><strong>עבירות מרמה:</strong> עבירות מרמה.</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    df = load_data()
    # OVERVIEW VISUALIZATION
    # Determine Y-axis max value before filtering
    years = ["כל השנים"] + sorted(df["Year"].dropna().unique().astype(int).tolist())
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
    if year_selected == "כל השנים":
        filtered_data = df
        crime_counts = (
            filtered_data.groupby("ReversedStatisticGroup").size()
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
        "\u202Bכלליות\nעבירות פליליות",
        "\u202Bוסדר ציבורי\nעבירות מוסר",
        "\u202Bביטחון\nעבירות",
        "\u202Bכלכליות ומנהליות\nעבירות",
        "\u202Bמרמה\nעבירות",
        "\u202Bתנועה\nעבירות"
    ]

    ticktext = [text[::-1] for text in ticktext]

    fixed_y_max = 18000  # Set this to an appropriate value for your dataset

    # Generate plot
    fig, ax = plt.subplots(figsize=(10, 6))

    if split_by_quarter:
        if year_selected == "כל השנים":
            grouped_data = (
                filtered_data.groupby(["ReversedStatisticGroup", "Quarter", "Year"])
                .size()
                .reset_index(name="Counts")
                .groupby(["ReversedStatisticGroup", "Quarter"])["Counts"]
                .sum()
                .reset_index()
            )
            max_y = grouped_data["Counts"].max()
        else:
            grouped_data = (
                filtered_data.groupby(["ReversedStatisticGroup", "Quarter"])
                .size()
                .reset_index(name="Counts")
            )
            max_y = 6000

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

        if year_selected == "כל השנים":
            ax.set_ylim(0, max_y + (0.1 * max_y))
        else:
            ax.set_ylim(0, 6000)

        ax.set_title("גוסו ןועבר יפל םיעשפה רפסמ", fontsize=16)
        ax.set_xlabel("עשפה גוס", fontsize=14)
        ax.set_ylabel("תוריבעה תומכ", fontsize=14)
        ax.set_xticks(range(len(ticktext)))
        ax.set_xticklabels(ticktext, rotation=0, ha='center', fontsize=12)
        ax.grid(axis='y', color='lightgrey', linewidth=0.5, zorder=0)

    else:
        crime_counts = crime_counts.reindex(unique_categories, fill_value=0)
        crime_counts.index = ticktext

        if year_selected == "כל השנים":
            max_y = crime_counts.max()
            ax.set_ylim(0, max_y + (0.1 * max_y))
        else:
            max_y = fixed_y_max
            ax.set_ylim(0, fixed_y_max)

        crime_counts.plot(kind="bar", ax=ax, color='orange', zorder=2)

        ax.set_xticks(range(len(ticktext)))
        ax.set_xticklabels(ticktext, rotation=0, ha='center', fontsize=12)
        ax.set_xlabel("עשפה גוס", fontsize=14)
        ax.set_ylabel("תוריבעה תומכ", fontsize=14)
        ax.grid(axis='y', color='lightgrey', linewidth=0.5)

    plt.tight_layout()
    st.pyplot(fig)






elif menu_option == 'השפעות מאורעות ה-7.10.2023 על התפלגות הפשיעה בישראל':
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

    st.markdown("""
    <div style="text-align: right; direction: rtl; font-size: 18px; line-height: 1.6;">
    הנתונים המוצגים בעמוד זה מתמקדים בהשוואת הפשיעה לפני ואחרי אירועי ה-7 באוקטובר 2023. 
    חלוקה זו מאפשרת להבין את השינויים שחלו במגמות הפשיעה בתקופה שלאחר האירועים ביחס לעבר.

    הגרף מציג את כמות העבירות המנורמלת לרבעון, תוך חלוקה לסוגי עבירות עיקריים, ומאפשר זיהוי הבדלים במגמות לאורך הזמן. 
    ניתן לסנן את המידע על פי מחוז משטרתי ולבחון כיצד הושפעו אזורים גיאוגרפיים שונים.

    מטרת הניתוח היא לספק תובנות מעמיקות על השלכות האירועים.
    </div>
    """, unsafe_allow_html=True)


    st.markdown("""
    <div style="text-align: right; direction: rtl; font-size: 18px; line-height: 1.8;">
    <h3>חלוקת עבירות לקבוצות</h3>
    במסגרת הניתוח, חילקנו את העבירות לקבוצות הבאות:
    <ul>
        <li><strong>עבירות פליליות כלליות:</strong> עבירות כלפי הרכוש, עבירות נגד גוף, עבירות נגד אדם, עבירות מין.</li>
        <li><strong>עבירות מוסר וסדר ציבורי:</strong> עבירות כלפי המוסר, עבירות סדר ציבורי.</li>
        <li><strong>עבירות ביטחון:</strong> עבירות ביטחון.</li>
        <li><strong>עבירות כלכליות ומנהליות:</strong> עבירות כלכליות, עבירות מנהליות, עבירות רשוי.</li>
        <li><strong>עבירות תנועה:</strong> עבירות תנועה.</li>
        <li><strong>עבירות מרמה:</strong> עבירות מרמה.</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
        <style>
        /* Style for the selectbox to reduce its width */
        div[data-testid="stSelectbox"] > div {
            width: 150px; /* Set the desired width for the dropdown */
        }

        /* Align the dropdown content */
        div[data-testid="stSelectbox"] {
            text-align: right;
            direction: rtl;
        }
        </style>
    """, unsafe_allow_html=True)
    col1, col2 = st.columns([1, 3])  # Adjust the ratio to move the dropdown to the right

    # Place the dropdown and label in the right column
    with col2:
        # Label for the dropdown
        st.markdown("""
            <div style="text-align: right; direction: rtl; font-size: 18px;">
                בחר מחוז:
            </div>
        """, unsafe_allow_html=True)

        # Dropdown menu
        selected_district = st.selectbox(
            "",
            districts,  # List of districts
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

elif menu_option == 'התפלגות סוגי עבירות לפי מרחבים משטרתיים':

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
    st.markdown("""
    <div style="text-align: right; direction: rtl; font-size: 18px; line-height: 1.6;">
    מפת החום מציגה את התפלגות הפשיעה במדינת ישראל בחלוקה לפי מרחבים משטרתיים. 
    ניתן לראות את המידע בצורה ויזואלית ולהבין אילו מרחבים סובלים יותר מפשיעה, ובאילו סוגי עבירות. 

    באמצעות הכלים האינטראקטיביים בדף זה, תוכלו לסנן את המידע לפי סוג העבירה והשנה המבוקשת, ולבחון את הפערים בין מרחבים שונים. 
    הניתוח מאפשר להעמיק את ההבנה בדבר המגמות הגיאוגרפיות של פשיעה במדינת ישראל.

    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align: right; direction: rtl; font-size: 18px; line-height: 1.8;">
    <h3>חלוקת עבירות לקבוצות</h3>
    במסגרת הניתוח, חילקנו את העבירות לקבוצות הבאות:
    <ul>
        <li><strong>עבירות פליליות כלליות:</strong> עבירות כלפי הרכוש, עבירות נגד גוף, עבירות נגד אדם, עבירות מין.</li>
        <li><strong>עבירות מוסר וסדר ציבורי:</strong> עבירות כלפי המוסר, עבירות סדר ציבורי.</li>
        <li><strong>עבירות ביטחון:</strong> עבירות ביטחון.</li>
        <li><strong>עבירות כלכליות ומנהליות:</strong> עבירות כלכליות, עבירות מנהליות, עבירות רשוי.</li>
        <li><strong>עבירות תנועה:</strong> עבירות תנועה.</li>
        <li><strong>עבירות מרמה:</strong> עבירות מרמה.</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

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