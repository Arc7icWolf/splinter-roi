import streamlit as st
import requests
import json
import pandas as pd
from io import BytesIO
from splinter_roi import check_rental_roi
from xlsxwriter import Workbook

# Mapping dictionaries
edition_mapping = {
    "Alpha Core": 0.1,
    "Promo": 2,
    "Beta Core": 1,
    "Beta, Untamed & Chaos Legion Reward": 3,
    "Untamed Core": 4,
    "Azmare Dice": 5,
    "Chaos Legion Core": 7,
    "Soulbound": 10,
    "Riftwatchers": 8,
    "Rebellion Core": 12,
    "Rebellion Reward": 13,
    "Conclave Arcana": 14
}

rarity_mapping = {
    "Common": 1,
    "Rare": 2,
    "Epic": 3,
    "Legendary": 4
}

color_mapping = {
    "Fire": "Red",
    "Water": "Blue",
    "Earth": "Green",
    "Life": "White",
    "Death": "Black",
    "Dragon": "Gold",
    "Neutral": "Gray"
}

foil_mapping = {
    "Regular": 0,
    "Gold": 1,
    "Gold Arcane": 2,
    "Black": 3,
    "Black Arcane": 4
}

# Function to apply conditional formatting
def highlight_roi(val):
    if val >= 30:
        color = 'lime'
    elif val >= 20:
        color = 'gold'
    elif val >= 10:
        color = 'orange'
    else:
        color = 'tomato'
    return f'background-color: {color}; color: black;'

# Function to convert DataFrame to Excel with conditional formatting
@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='ROI Results')
        workbook = writer.book
        worksheet = writer.sheets['ROI Results']

        format_decimal = workbook.add_format({'num_format': '0.00'})
        worksheet.set_column('A:Z', 18, format_decimal)

        roi_col_idx = df.columns.get_loc('roi')
        roi_col_letter = chr(65 + roi_col_idx)

        worksheet.conditional_format(f'{roi_col_letter}2:{roi_col_letter}1048576', {
            'type': 'cell',
            'criteria': '>=',
            'value': 30,
            'format': workbook.add_format({'bg_color': 'lime', 'font_color': 'black'})
        })
        worksheet.conditional_format(f'{roi_col_letter}2:{roi_col_letter}1048576', {
            'type': 'cell',
            'criteria': 'between',
            'minimum': 20,
            'maximum': 29.99,
            'format': workbook.add_format({'bg_color': 'gold', 'font_color': 'black'})
        })
        worksheet.conditional_format(f'{roi_col_letter}2:{roi_col_letter}1048576', {
            'type': 'cell',
            'criteria': 'between',
            'minimum': 10,
            'maximum': 19.99,
            'format': workbook.add_format({'bg_color': 'orange', 'font_color': 'black'})
        })
        worksheet.conditional_format(f'{roi_col_letter}2:{roi_col_letter}1048576', {
            'type': 'cell',
            'criteria': '<',
            'value': 9.99,
            'format': workbook.add_format({'bg_color': 'tomato', 'font_color': 'black'})
        })

    return output.getvalue()

# Streamlit application
def main():
    st.set_page_config(
        page_title="SplinterROI",
        page_icon="🛠️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.sidebar.header("Card Filters 🃏")

    editions = st.sidebar.multiselect(
        "Select Editions:",
        options=list(edition_mapping.keys()),
        default=["Conclave Arcana"]
    )

    card_types = st.sidebar.multiselect(
        "Select Card Types:",
        options=["Summoner", "Monster"],
        default=["Monster"]
    )

    rarities = st.sidebar.multiselect(
        "Select Rarities:",
        options=list(rarity_mapping.keys()),
        default=["Legendary"]
    )

    colors = st.sidebar.multiselect(
        "Select Colors:",
        options=list(color_mapping.keys()),
        default=[]
    )

    foils = st.sidebar.multiselect(
        "Select Foils:",
        options=list(foil_mapping.keys()),
        default=["Regular"]
    )

    bcx = st.sidebar.number_input("BCX Amount:", min_value=1, value=1, step=1)

    if st.sidebar.button("Calculate ROI 📊"):
        if not (editions and card_types and rarities and bcx):
            st.sidebar.error("Please fill in all required filters (Editions, Card Types, Rarities, BCX)!")
        else:
            editions_ids = [str(edition_mapping[e]) for e in editions]
            rarities_ids = [rarity_mapping[r] for r in rarities]
            colors_ids = [color_mapping[c] for c in colors] if colors else []
            foils_ids = [foil_mapping[t] for t in foils]

            with st.spinner("Processing cards and calculating ROI..."):
                try:
                    session = requests.Session()
                    data = check_rental_roi(
                        editions_ids,
                        card_types,
                        rarities_ids,
                        foils_ids,
                        bcx,
                        colors_ids,
                        session
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    st.error(f"Data parsing error: {e}")
                    return
                except Exception as e:
                    st.error(f"Unexpected error: {e}")
                    return

            if not data:
                st.warning("No results found with the selected parameters.")
                return

            df = pd.DataFrame(data)
            # Converti 'roi' in numerico e gestisci "N/A"
            df['roi'] = pd.to_numeric(df['roi'], errors='coerce')
            # Ordina con NaN in fondo
            df = df.sort_values(by='roi', ascending=False, na_position='last').reset_index(drop=True)

            st.markdown("## ROI Results 📈")
            st.dataframe(
                df.style.format({
                    'roi': lambda x: '{:.2f}'.format(x) if pd.notnull(x) else 'N/A',  # Formatta i NaN come "N/A"
                    'rental_rate': '{:.4f}'
                }).applymap(highlight_roi, subset=['roi']),
                height=600
            )

            excel_data = convert_df_to_excel(df)
            st.download_button(
                label="🗃️ Download results as Excel",
                data=excel_data,
                file_name='splinterlands_roi.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

            st.bar_chart(df.set_index('name')['roi'])

    st.markdown("---")
    st.title("SplinterROI 🛠️")
    st.caption("Advanced ROI filtering for Splinterlands card rentals")
    st.write(
        "Use the filters on the left sidebar to select cards and calculate their rental ROI."
    )

if __name__ == "__main__":
    main()
