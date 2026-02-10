import streamlit as st
import requests
import json
import pandas as pd
from io import BytesIO
from splinter_roi import check_rental_roi
from xlsxwriter import Workbook
from icons import edition_icons, card_type_icons, rarity_icons, color_icons
from concurrent.futures import ThreadPoolExecutor, TimeoutError

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
    "Conclave Arcana Core": 14,
    "Conclave Arcana Extra": 17,
    "Conclave Arcana Reward": 18,
    "Escalation": 20,
}

rarity_mapping = {"Common": 1, "Rare": 2, "Epic": 3, "Legendary": 4}

color_mapping = {
    "Fire": "Red",
    "Water": "Blue",
    "Earth": "Green",
    "Life": "White",
    "Death": "Black",
    "Dragon": "Gold",
    "Neutral": "Gray",
}

foil_mapping = {
    "Regular": 0,
    "Gold": 1,
    "Gold Arcane": 2,
    "Black": 3,
    "Black Arcane": 4,
}

rental_length_mapping = {
    "Long": 0,
    "Medium": 1,
    "Short": 2
}

# Function to apply conditional formatting
def highlight_roi(val):
    try:
        val_float = float(val)
    except (ValueError, TypeError):
        # Se non convertibile, considera come NaN
        return "background-color: tomato; color: black;"
    if pd.isna(val_float):
        return "background-color: tomato; color: black;"
        
    if val >= 30:
        color = "lime"
    elif val >= 20:
        color = "gold"
    elif val >= 10:
        color = "orange"
    else:
        color = "tomato"
    return f"background-color: {color}; color: black;"


def format_roi(x):
    try:
        return "{:.2f}".format(float(x))
    except (ValueError, TypeError):
        return "N/A"


# Streamlit application
def main():
    st.set_page_config(
        page_title="SplinterROI",
        page_icon="🛠️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        <style>
            /* Applica larghezza piena a tutte le tabelle */
            table {
                width: 100% !important;
                table-layout: auto;
            }
    
            /* Scroll orizzontale per il contenitore della tabella */
            .stMarkdown > div {
                overflow-x: auto;
            }
    
            /* Opzionale: imposta una larghezza minima per le colonne */
            th, td {
                min-width: 80px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


    st.sidebar.header("Card Filters 🃏")

    editions = st.sidebar.multiselect(
        "Select Editions:",
        options=list(edition_mapping.keys()),
        default=["Conclave Arcana Core"],
    )

    card_types = st.sidebar.multiselect(
        "Select Card Types:", options=["Arcon", "Monster"], default=["Monster"]
    )

    rarities = st.sidebar.multiselect(
        "Select Rarities:", options=list(rarity_mapping.keys()), default=["Legendary"]
    )

    colors = st.sidebar.multiselect(
        "Select Colors (optional):", options=list(color_mapping.keys()), default=[]
    )

    foil = st.sidebar.selectbox(
        "Select a Foil:", options=list(foil_mapping.keys()), index=0
    )

    bcx = st.sidebar.number_input("BCX Amount (insert 38 for Gold Arcane, Black and Black Arcane):", min_value=1, value=1, step=1)

    rental_length = st.sidebar.selectbox(
        "Select Rental Length:", options=list(rental_length_mapping.keys()), index=0
    )

    if st.sidebar.button("Calculate ROI 📊"):
        if not (editions and card_types and rarities and foil and bcx and rental_length):
            st.sidebar.error(
                "Please fill in all required filters (Editions, Card Types, Rarities, Foil, BCX, Rental Lenght)!"
            )
        else:
            editions_ids = [str(edition_mapping[e]) for e in editions]
            rarities_ids = [rarity_mapping[r] for r in rarities]
            colors_ids = [color_mapping[c] for c in colors] if colors else []
            foil_id = foil_mapping[foil]
            rental_length_id = rental_length_mapping[rental_length]
            card_types = ["Summoner" if x == "Archon" else x for x in card_types]
            st.write(card_types)

            data = []

            with st.spinner("Processing cards and calculating ROI..."):
                with requests.Session() as session, ThreadPoolExecutor() as executor:                    
                    future = executor.submit(
                        check_rental_roi, 
                        editions_ids,
                        card_types,
                        rarities_ids,
                        foil_id,
                        bcx,
                        colors_ids,
                        rental_length_id,
                        session,
                    )

                    try:
                        data = future.result(timeout=60)
                    except TimeoutError:
                        st.write(
                            "Your query is requiring too much time: this might be due to a too complex query (try selecting more filters) or an unresponsive API (try again in a few minutes)"
                        )
                        return
                    except (json.JSONDecodeError, KeyError) as e:
                        st.error(f"Data parsing error: {e}")
                        return
                    except Exception as e:
                        st.error(f"Unexpected error: {e}")
                        return

            if not data:
                st.warning("No results found with the selected parameters.")
                return

            for d in data:
                d["Card"] = f"{d['icons']} - {d['name']}"

            df = pd.DataFrame(data)
            
            # Rinomina colonne per visualizzazione
            df = df.rename(columns={
                "roi": "ROI",
                "avg rental price": "Rental Price (avg)",
                "cards rented": "Amount of Cards Rented"
            })
            
            # Crea una colonna 'roi' numerica per ordinamento e highlight
            df["roi"] = pd.to_numeric(df["ROI"], errors="coerce")
            
            # Ordina con NaN in fondo
            df = df.sort_values(by="roi", ascending=False, na_position="last").reset_index(drop=True)
            
            # Mostra i risultati
            st.markdown("## ROI Results 📈")
            
            # Colonne da mostrare
            columns_to_show = ["Card", "ROI", "Rental Price (avg)", "Amount of Cards Rented"]
            
            st.write(
                df[columns_to_show]
                .style.format({
                    "ROI": format_roi,
                    "Rental Price (avg)": "{:.4f}",
                })
                .applymap(highlight_roi, subset=["ROI"])  # highlight sulla colonna visibile
                .to_html(escape=False),
                unsafe_allow_html=True,
            )
            
            # Bar chart
            st.bar_chart(df.set_index("name")["roi"])


    st.markdown("---")
    st.title("SplinterROI 🛠️")
    st.caption("Advanced ROI filtering for Splinterlands card rentals")
    st.write(
        "Use the filters on the left sidebar to select cards and calculate their rental ROI."
    )


if __name__ == "__main__":
    main()
