##############################################################
# Top of File
# ###################################################


import streamlit as st

USERNAME = "admin"
PASSWORD = "UFPRO123"

def login():

    st.title("🔐 UltraPRO Login")

    username = st.text_input("Username")
    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button("Login"):

        if (
            username == USERNAME
            and
            password == PASSWORD
        ):

            st.session_state["authenticated"] = True

            st.rerun()

        else:

            st.error(
                "Invalid Username or Password"
            )


###########################################################################

st.markdown("""
<style>

/* Reduce page width */

.main .block-container{
    max-width: 1200px;
    padding-top: 1rem;
    padding-bottom: 1rem;
}

/* Larger section headers */

h3{
    font-size: 26px !important;
}

/* Larger labels */

label{
    font-size:16px !important;
    font-weight:600 !important;
}

/* Bigger metric values */

[data-testid="stMetricValue"]{
    font-size:36px !important;
}

/* Bigger metric label */

[data-testid="stMetricLabel"]{
    font-size:18px !important;
}

/* Wider number inputs */

div[data-testid="stNumberInput"]{
    max-width:250px !important;
}

</style>
""", unsafe_allow_html=True)


########################################################################################################################################################

from reportlab.pdfgen import canvas
from io import BytesIO
import streamlit as st
import pandas as pd
import math
from streamlit_option_menu import option_menu

import math
#########################################################

module_name = st.session_state.get("selected_module")
feed_flow = st.session_state.get("uf_feed_flow")

net_filtrate = st.session_state.get("net_filtrate")
gross_filtrate = st.session_state.get("gross_filtrate")

acid_dose = st.session_state.get("acid_dose_mgl")
alkali_dose = st.session_state.get("alkali_dose_mgl")
naocl_dose = st.session_state.get("naocl_dose_mgl")

import base64
import os

# =====================================================
# IMAGE
# =====================================================

def get_image_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(
            f.read()
        ).decode()


# =====================================================
# VALUES
# =====================================================
# =====================================================
# NaOH(50%) Feed Rate (gal/h)
# =====================================================

def calc_naoh50_gph(
        flow_gpm,
        dose_mgl
):

    # Convert flow to L/hr
    flow_lph = (
        flow_gpm *
        3.78541 *
        60
    )

    # Pure NaOH required (kg/hr)
    pure_naoh_kgph = (
        dose_mgl *
        flow_lph
    ) / 1000000

    # 50% Solution
    solution_kgph = (
        pure_naoh_kgph /
        0.50
    )

    # Density of 50% NaOH
    density = 1.53

    # Convert to gal/hr
    gph = (
        solution_kgph /
        density /
        3.785
    )

    return gph

###################################################################
# =====================================================
# CARBONATE SPECIATION
# =====================================================

def carbonate_speciation(
        hco3_mgl,
        co3_mgl,
        co2_mgl,
        ph
):

    # mg/L → mmol/L

    hco3_mmol = hco3_mgl / 61.0
    co3_mmol = co3_mgl / 60.0
    co2_mmol = co2_mgl / 44.0

    tic = (
        hco3_mmol +
        co3_mmol +
        co2_mmol
    )

    h = 10 ** (-ph)

    k1 = 10 ** (-6.35)
    k2 = 10 ** (-10.33)

    denom = (
        h**2 +
        k1 * h +
        k1 * k2
    )

    alpha0 = (h**2) / denom
    alpha1 = (k1 * h) / denom
    alpha2 = (k1 * k2) / denom

    co2 = tic * alpha0
    hco3 = tic * alpha1
    co3 = tic * alpha2

    return (
        co2,
        hco3,
        co3
    )

# =====================================================
# BORON
# =====================================================

def borate_alkalinity(
        boron_mgl,
        ph
):

    pka = 9.24

    fraction = (
        1 /
        (
            1 +
            10 ** (pka - ph)
        )
    )

    return (
        boron_mgl *
        fraction /
        10.81
    )

# =====================================================
# SILICA
# =====================================================

def silica_alkalinity(
        silica_mgl,
        ph
):

    pka = 9.8

    fraction = (
        1 /
        (
            1 +
            10 ** (pka - ph)
        )
    )

    return (
        silica_mgl *
        fraction /
        60.08
    )

# =====================================================
# NH4 / NH3
# =====================================================

def ammonia_alkalinity(
        nh4_mgl,
        ph
):

    pka = 9.25

    fraction = (
        1 /
        (
            1 +
            10 ** (pka - ph)
        )
    )

    return (
        nh4_mgl *
        fraction /
        18.04
    )

# =====================================================
# TOTAL ALKALINITY
# =====================================================

def calculate_alkalinity(
        hco3,
        co3,
        boron,
        silica,
        nh4,
        ph
):

    carbonate_alk = (
        hco3 * 50 / 61
    ) + (
        co3 * 50 / 30
    )

    borate_alk = (
        borate_alkalinity(
            boron,
            ph
        ) * 50
    )

    silica_alk = (
        silica_alkalinity(
            silica,
            ph
        ) * 50
    )

    ammonia_alk = (
        ammonia_alkalinity(
            nh4,
            ph
        ) * 50
    )

    return (
        carbonate_alk
        + borate_alk
        + silica_alk
        + ammonia_alk
    )

# =====================================================
# CHEMICAL CALCULATION
# =====================================================

def calculate_ceb_chemicals(
        ph,
        hco3,
        co3,
        co2,
        boron,
        silica,
        nh4,
        temperature_c=25
):

    # If no water data exists

    if (
        hco3 == 0 and
        co3 == 0 and
        co2 == 0
    ):

        return {

            "alkalinity": 0,

            "hcl32_mgL": 0,

            "naoh50_mgL": 0,

            "naocl12_mgL": 350
        }

    alkalinity = calculate_alkalinity(
        hco3,
        co3,
        boron,
        silica,
        nh4,
        ph
    )

    alkalinity_meq = (
        alkalinity / 50.0
    )

    # -----------------------------------------
    # HCl demand to pH 2
    # -----------------------------------------

    hco3_meq = hco3 / 61.0

    co3_meq = co3 / 30.0

    acid_meq = (
        alkalinity_meq
        + 10.0
    )

    pure_hcl_mgl = (
        acid_meq * 36.46
    )

    hcl32_mgl = (
        pure_hcl_mgl / 1
    )

    # -----------------------------------------
    # NaOH demand to pH 12
    # -----------------------------------------

    co2_meq = (
        co2 / 44.0
    )

    base_meq = (
        alkalinity_meq
        + co2_meq
        + 10.0
    )

    pure_naoh_mgl = (
        base_meq * 40.0
    )

    naoh50_mgl = (
        pure_naoh_mgl / 1
    )

    return {

        "alkalinity": alkalinity,

        "hcl32_mgL": hcl32_mgl,

        "naoh50_mgL": naoh50_mgl,

        "naocl12_mgL": 350

    }

########################################################################################################################################################

show_debug = False

if show_debug:
    import uuid

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())

    st.sidebar.write(
        "Session ID:",
        st.session_state["session_id"]
    )

st.set_page_config(
    page_title="UltraPRO",
    page_icon="🔷",
    layout="wide"
)
##############################################################################################################
#LOGIN

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login()
    st.stop()


#LOGOUT

with st.sidebar:

    if st.button("🚪 Logout"):

        st.session_state["authenticated"] = False

        st.rerun()


#############################################################################################################
show_debug = False

if show_debug:
    import uuid

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())

    st.sidebar.write(
        "Session ID:",
        st.session_state["session_id"]
    )


####################################################
# Box size reduction
##########################################
st.markdown("""
<style>

/* Reduce width of Number Inputs */

div[data-testid="stNumberInput"] {
    max-width: 180px !important;
}

/* Reduce width of Select Boxes */

div[data-testid="stSelectbox"] {
    max-width: 180px !important;
}

/* Center value */

div[data-testid="stNumberInput"] input {
    text-align: center;
}

</style>
""", unsafe_allow_html=True)

###########################################################################
# box closer
###########################################################################

st.markdown("""
<style>

.main .block-container {
    max-width: 1100px;
    padding-top: 1rem;
    padding-bottom: 1rem;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# SESSION DEFAULTS
# =====================================================


defaults = {

    # Feed Water Analysis

    "ca": 0.0,
    "mg": 0.0,
    "na": 0.0,
    "k": 0.0,

    "ba": 0.0,
    "sr": 0.0,

    "hco3": 0.0,
    "co3": 0.0,
    "so4": 0.0,
    "cl": 0.0,
    "no3": 0.0,

    "fluoride": 0.0,

    "silica": 0.0,
    "boron": 0.0,

    "iron": 0.0,
    "manganese": 0.0,

    "temperature": 25.0,
    "feed_ph": 7.0,

    # Calculated Values
    "calculated_tds": 0.0,
    "hardness": 0.0,
    "conductivity": 0.0,
    "feed_op": 0.0,
    "alkalinity": 0.0,

    # UF Design
    "uf_feed_flow": 50.0,
    "uf_recovery": 95.0,
    "uf_flux_gfd": 35.3,      # GFD
    "uf_backwash": 8.0,  # %
    "uf_cip_frequency": 30,  # days

    "water_type": "Municipal Water",

    # UF Module
    "uf_module_area": 77.0,  # m²/module
    "uf_design_flux": 35.3,  # GFD
    "uf_max_tmp": 2.1,  # bar
    "uf_backwash_gfd": 70.7,      # GFD
    "uf_air_scour": 15.0,  # Nm³/hr

    "racks_per_unit": 1,
    "modules_per_rack": 18,
    "online_units": 2,
    "standby_units": 0,
    "redundant_units": 1,

    "trains_online": 2,
    "standby_trains": 1,

    "uf_technology_saved": "PVDF Out-In",
    "uf_module_saved": "IntegraTec XP 77 IP"

}



for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value



# Default page




    ####################################################################
    # SIDE BAR
    ####################################################################

with st.sidebar:



    st.markdown("### UF")

    menu_options = [
        "Feed Water",
        "Design",
        "Configuration",
        "Backwash",
        "CEB",
        "CIP",
        "Additional Settings",
        "Effluent Water",
        "Summary"

    ]

    menu_icons = [
        "droplet",
        "diagram-3",
        "gear",
        "arrow-repeat",
        "beaker",
        "tools",
        "sliders",
        "droplet-fill",
        "file-earmark-text"
    ]

    page = option_menu(
        menu_title=None,
        options=menu_options,
        icons=menu_icons,
        key="page"
    )



    ####################################################################
    # Dashboard
    ####################################################################

    if page == "Dashboard":
        st.title("🔷 UltraPRO")

        feed_flow = st.session_state.get(
            "uf_feed_flow",
            50.0
        )

        recovery = st.session_state.get(
            "uf_recovery",
            95.0
        )

        permeate = feed_flow * recovery / 100
        backwash = feed_flow - permeate


        ########################################################
        # UF Flow Diagram
        ########################################################

        feed_flow = st.session_state.get("uf_feed_flow", 50.0)
        recovery = st.session_state.get("uf_recovery", 95.0)

        permeate = feed_flow * recovery / 100
        backwash = feed_flow - permeate

        st.components.v1.html(
            f"""
        <style>
    
        .flow-container {{
            position: relative;
            width: 100%;
            height: 320px;
            background: #f8f9fa;
            border: 1px solid #d3d3d3;
            border-radius: 10px;
        }}
    
        .box {{
            position: absolute;
            width: 170px;
            padding: 12px;
            text-align: center;
            border-radius: 8px;
            font-weight: bold;
            border: 1px solid #90c8c5;
        }}
    
        .feed {{
            left: 20px;
            top: 110px;
            background: #dff4f3;
        }}
    
        .uf {{
            left: 340px;
            top: 110px;
            background: #dff4f3;
        }}
    
        .product {{
            right: 20px;
            top: 110px;
            background: #dff4f3;
        }}
    
        .backwash {{
            left: 340px;
            top: 220px;
            background: #ffe6d5;
        }}
    
        .arrow-h {{
            position:absolute;
            height:4px;
            background:#00a99d;
        }}
    
        .arrow-v {{
            position:absolute;
            width:4px;
            background:#ff6600;
        }}
    
        .label {{
            position:absolute;
            font-size:12px;
            font-weight:bold;
        }}
    
        </style>
    
        <div class="flow-container">
    
            <div class="box feed">
                💧 Feed Water<br>
                {feed_flow:.2f} m³/hr
            </div>
    
            <div class="box uf">
                🛡️ UF System
            </div>
    
            <div class="box product">
                ✅ UF Permeate<br>
                {permeate:.2f} m³/hr
            </div>
    
            <div class="box backwash">
                🔄 Backwash/Waste<br>
                {backwash:.2f} m³/hr
            </div>
    
            <!-- Feed to UF -->
            <div class="arrow-h"
                 style="left:190px; top:145px; width:150px;">
            </div>
    
            <!-- UF to Product -->
            <div class="arrow-h"
                 style="left:510px; top:145px; width:120px;">
            </div>
    
            <!-- UF to Backwash -->
            <div class="arrow-v"
                 style="left:425px; top:170px; height:50px;">
            </div>
    
            <div class="label"
                 style="left:240px; top:120px;">
                 Feed
            </div>
    
            <div class="label"
                 style="left:555px; top:120px;">
                 Permeate
            </div>
    
            <div class="label"
                 style="left:440px; top:190px;">
                 Backwash
            </div>
    
        </div>
        """,
            height=340
        )
# =====================================================
# FEED WATER ANALYSIS
# ====================================================
if page == "Feed Water":


    st.title("💧 Feed Water ")

    # Upload data from library>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

    uploaded_file = st.file_uploader(
        "Upload IMS Water Analysis",
        type=["xlsx"]
    )

    if st.button("📂 Load IMS Water Analysis"):

        if uploaded_file is None:

            st.warning("Please select IMS Excel file")

        else:

            df = pd.read_excel(
                uploaded_file,
                header=1,
                engine="openpyxl"
            )

           # st.write(df.head(30))
           # st.write(df.columns.tolist())



            # Remove blank rows
            df = df.dropna(how="all")

            # Create dictionary
            water_dict = dict(
                zip(
                    df["Species"].astype(str).str.strip(),
                    df["Raw water"]
                )
            )

            # Auto populate session state

            st.session_state["ca"] = water_dict.get(
                "Calcium",
                0
            )

            st.session_state["mg"] = water_dict.get(
                "Magnesium",
                0
            )

            st.session_state["na"] = water_dict.get(
                "Sodium",
                0
            )

            st.session_state["k"] = water_dict.get(
                "Potassium",
                0
            )

            st.session_state["sr"] = water_dict.get(
                "Strontium",
                0
            )

            st.session_state["ba"] = water_dict.get(
                "Barium",
                0
            )

            st.session_state["fluoride"] = water_dict.get(
                "Fluoride",
                0
            )

            st.session_state["cl"] = water_dict.get(
                "Chloride",
                0
            )

            st.session_state["so4"] = water_dict.get(
                "Sulfate",
                0
            )

            st.session_state["no3"] = water_dict.get(
                "Nitrate",
                0
            )

            st.session_state["co3"] = water_dict.get(
                "Carbonate",
                0
            )

            st.session_state["hco3"] = water_dict.get(
                "Bicarbonate",
                0
            )

            st.session_state["boron"] = water_dict.get(
                "Boron",
                0
            )

            st.session_state["silica"] = water_dict.get(
                "Silica",
                0
            )

            st.session_state["pH"] = water_dict.get(
                "pH",
                7
            )

            st.session_state["CO2"] = water_dict.get(
                "CO2",
                7
            )


            st.session_state["TDS"] = water_dict.get(
                "TDS",
                0
            )

            st.session_state["Turbidity"] = water_dict.get(
                "Turbidity",
                0
            )

            st.session_state["TSS"] = water_dict.get(
                "TSS",
                0
            )

            st.session_state["TOC"] = water_dict.get(
                "TOC",
                0
            )

            st.session_state["SDI"] = water_dict.get(
                "SDI",
                0
            )

            #######################################
            st.session_state["ca_widget"] = st.session_state["ca"]
            st.session_state["mg_widget"] = st.session_state["mg"]
            st.session_state["na_widget"] = st.session_state["na"]
            st.session_state["k_widget"] = st.session_state["k"]

            st.session_state["sr_widget"] = st.session_state["sr"]
            st.session_state["ba_widget"] = st.session_state["ba"]

            st.session_state["hco3_widget"] = st.session_state["hco3"]
            st.session_state["co3_widget"] = st.session_state["co3"]

            st.session_state["so4_widget"] = st.session_state["so4"]
            st.session_state["cl_widget"] = st.session_state["cl"]

            st.session_state["no3_widget"] = st.session_state["no3"]
            st.session_state["fluoride_widget"] = st.session_state["fluoride"]

            st.session_state["silica_widget"] = st.session_state["silica"]
            st.session_state["boron_widget"] = st.session_state["boron"]

            st.session_state["CO2_widget"] = st.session_state["CO2"]
            st.session_state["TDS_widget"] = st.session_state["TDS"]
            st.session_state["Turbidity_widget"] = st.session_state["Turbidity"]
            st.session_state["TSS_widget"] = st.session_state["TSS"]
            st.session_state["TOC_widget"] = st.session_state["TOC"]


            st.session_state["feed_ph_widget"] = st.session_state["feed_ph"]




            st.success(
                "✅ IMS Water Analysis Loaded Successfully"
            )




           # st.rerun()


            #######################################################


    ##########################################>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    st.markdown("### Feed Parameters")

    p1, p2, p3 = st.columns(3)
    with p1:

        water_types = [
            "UF Permeate",
            "Softened Water",
            "Well Water",
            "Ground Water",
            "Municipal Water",
            "Surface Water",
            "Brackish Water",
            "Sea Water"
        ]

        water_type = st.selectbox(
            "Water Type",
            water_types,
            index=water_types.index(
                st.session_state["water_type"]
            ),
            key="water_type_widget"
        )



        st.session_state["water_type"] = water_type

        sdi_requirements = {
            "UF Permeate": ("SDI < 1", "green"),
            "Softened Water": ("SDI < 3", "green"),
            "Well Water": ("SDI < 3", "green"),
            "Ground Water": ("SDI < 3", "green"),
            "Municipal Water": ("SDI < 5", "orange"),
            "Surface Water": ("SDI < 5", "orange"),
            "Brackish Water": ("Membrane Pretreatment, SDI < 3", "red"),
            "Sea Water": ("Conventional Pretreatment + UF, SDI < 3", "red")
        }

        sdi_text, sdi_color = sdi_requirements[water_type]

        st.markdown(
            f"""
            <div style="
                padding:12px;
                border-radius:10px;
                background-color:{sdi_color};
                color:white;
                font-weight:bold;
                text-align:center;
            ">
            Recommended Feed Requirement: {sdi_text}
            </div>
            """,
            unsafe_allow_html=True
        )
    # =================================================
    # CATIONS
    # =================================================

    st.subheader("Feed Water Analysis")

    c1, c2, c3 = st.columns(
        [1, 1, 1],
        gap="small"
    )

    with c1:
        ca = st.number_input(
            "Calcium (Ca) mg/L",
            value=st.session_state["ca"],
            key="ca_widget"
        )
        st.session_state["ca"] = ca

        mg = st.number_input(
            "Magnesium (Mg) mg/L",
            value=st.session_state["mg"],
            key="mg_widget"
        )
        st.session_state["mg"] = mg

        na = st.number_input(
            "Sodium (Na) mg/L",
            value=st.session_state["na"],
            key="na_widget"
        )
        st.session_state["na"] = na

        k = st.number_input(
            "Potassium (K) mg/L",
            value=st.session_state["k"],
            key="k_widget"
        )
        st.session_state["k"] = k

        ba = st.number_input(
            "Barium (Ba) mg/L",
            value=st.session_state["ba"],
            key="ba_widget"
        )
        st.session_state["ba"] = ba

        sr = st.number_input(
            "Strontium (Sr) mg/L",
            value=st.session_state["sr"],
            key="sr_widget"
        )
        st.session_state["sr"] = sr

        # =================================================
        # ANIONS
        # =================================================

    with c2:
            hco3 = st.number_input(
                "Bicarbonate (HCO3) mg/L",
                value=st.session_state["hco3"],
                key="hco3_widget"
            )
            st.session_state["hco3"] = hco3

            co3 = st.number_input(
                "Carbonate (CO3) mg/L",
                value=st.session_state["co3"],
                key="co3_widget"
            )
            st.session_state["co3"] = co3

            so4 = st.number_input(
                "Sulphate (SO4) mg/L",
                value=st.session_state["so4"],
                key="so4_widget"
            )
            st.session_state["so4"] = so4

            cl = st.number_input(
                "Chloride (Cl) mg/L",
                value=st.session_state["cl"],
                key="cl_widget"
            )
            st.session_state["cl"] = cl

            no3 = st.number_input(
                "Nitrate (NO3) mg/L",
                value=st.session_state["no3"],
                key="no3_widget"
            )
            st.session_state["no3"] = no3

            fluoride = st.number_input(
                "Fluoride (F) mg/L",
                value=st.session_state["fluoride"],
                key="fluoride_widget"
            )
            st.session_state["fluoride"] = fluoride

        # =================================================
        # NEUTRALS
        # =================================================

    with c3:
            silica = st.number_input(
                "Silica (SiO2) mg/L",
                value=st.session_state["silica"],
                key="silica_widget"
            )
            st.session_state["silica"] = silica

            boron = st.number_input(
                "Boron (B) mg/L",
                value=st.session_state["boron"],
                key="boron_widget"
            )
            st.session_state["boron"] = boron

            iron = st.number_input(
                "Iron (Fe) mg/L",
                value=st.session_state["iron"],
                key="iron_widget"
            )
            st.session_state["iron"] = iron

            manganese = st.number_input(
                "Manganese (Mn) mg/L",
                value=st.session_state["manganese"],
                key="manganese_widget"
            )
            st.session_state["manganese"] = manganese

            temperature = st.number_input(
                "Temperature (°C)",
                value=st.session_state["temperature"],
                key="temperature_widget"
            )
            st.session_state["temperature"] = temperature

            ph = st.number_input(
                "pH",
                value=st.session_state["feed_ph"],
                key="feed_ph_widget"
            )
            st.session_state["feed_ph"] = ph
###################################################################################
    p1, p2, p3 = st.columns(3)

    with p2:
        Turbidity = st.number_input(
            "Turbidity (NTU)",
            value=st.session_state.get(
                "Turbidity",
                0.0
            ),
            key="Turbidity_widget"
        )

        st.session_state["Turbidity"] = Turbidity

        TSS = st.number_input(
            "TSS (mg/L)",
            value=st.session_state.get(
                "TSS",
                0.0
            ),
            key="TSS_widget"
        )

        st.session_state["TSS"] = TSS

        sdi = st.number_input(
            "SDI15",
            value=st.session_state.get(
                "sdi",
                0.0
            ),
            key="sdi_widget"
        )

        st.session_state["sdi"] = sdi

    with p3:
        TOC = st.number_input(
            "TOC (mg/L)",
            value=st.session_state.get(
                "TOC",
                0.0
            ),
            key="TOC_widget"
        )

        st.session_state["TOC"] = TOC

        design_flow = st.number_input(
            "UF Feed Flow (m³/hr)",
            value=st.session_state.get(
                "uf_feed_flow",
                50.0
            ),
            key="uf_feed_flow_widget"
        )

        st.session_state["uf_feed_flow"] = design_flow
    ################################# ##########################################
    #############################################################################################
    # Save values permanently
    ######################################################################################
    total_cations = (
                ca + mg + na + k +
                ba + sr + iron +
                manganese
    )

    total_anions = (
                hco3 + co3 +
                so4 + cl +
                no3 + fluoride
    )

    tds = (
                total_cations +
                total_anions +
                silica +
                boron
    )

    hardness = (
                ca * 2.497 +
                mg * 4.118
    )

    conductivity = tds * 2

    ############################################################

    # ==========================================
    # CHARGE BALANCE
    # ==========================================

    # Cations (meq/L)

    ca_meq = ca / 20.04
    mg_meq = mg / 12.15
    na_meq = na / 23.00
    k_meq = k / 39.10

    ba_meq = ba / 68.67
    sr_meq = sr / 43.81

    # Anions (meq/L)

    hco3_meq = hco3 / 61.00
    co3_meq = co3 / 30.00
    so4_meq = so4 / 48.00
    cl_meq = cl / 35.45
    no3_meq = no3 / 62.00
    fluoride_meq = fluoride / 19.00

    total_cation_meq = (
                ca_meq +
                mg_meq +
                na_meq +
                k_meq +
                ba_meq +
                sr_meq
        )

    total_anion_meq = (
                hco3_meq +
                co3_meq +
                so4_meq +
                cl_meq +
                fluoride_meq
        )

    if (total_cation_meq + total_anion_meq) > 0:

            charge_balance_error = (
                                           (
                                                   total_cation_meq -
                                                   total_anion_meq
                                           )
                                           /
                                           (
                                                   total_cation_meq +
                                                   total_anion_meq
                                           )
                                   ) * 100

    else:

            charge_balance_error = 0
######################################
    st.subheader("UF Feed Assessment")

    if Turbidity > 50:
        st.warning(
            "⚠ High Turbidity - Consider clarification before UF"
        )

    if sdi > 5:
        st.warning(
            "⚠ High SDI may reduce UF performance"
        )

    if iron > 0.3:
        st.warning(
            "⚠ Iron may increase membrane fouling"
        )

    if manganese > 0.1:
        st.warning(
            "⚠ Manganese may increase membrane fouling"
        )

    if TOC > 10:
        st.warning(
            "⚠ High TOC may increase CEB/CIP frequency"
        )
    ###############################################################################
    # KPI
    ###################################################################
    cb1, cb2, cb3 = st.columns(3)

    cb1.metric(
            "Cations (meq/L)",
            f"{total_cation_meq:.2f}"
    )

    cb2.metric(
            "Anions (meq/L)",
            f"{total_anion_meq:.2f}"
    )

    cb3.metric(
            "Charge Balance %",
            f"{charge_balance_error:.2f}"
    )

    u1, u2, u3, u4 = st.columns(4)

    u1.metric(
            "Turbidity",
            f"{Turbidity:.2f} NTU"
    )

    u2.metric(
            "TSS",
            f"{TSS:.2f} mg/L"
    )

    u3.metric(
            "SDI",
            f"{sdi:.2f}"
    )

    u4.metric(
            "TOC",
            f"{TOC:.2f} mg/L"
    )

    #############################################################
    # Status
    ######################################################

    if abs(charge_balance_error) <= 5:

        st.success(
            "✅ Charge Balance ACCEPTABLE"
        )

    elif abs(charge_balance_error) <= 10:

        st.warning(
            "⚠ Charge Balance Needs Review"
        )

    else:

        st.error(
            "❌ Charge Balance FAILED"
        )

    ####################################################################################

    # -----------------------------------
    # AUTO BALANCE
    # -----------------------------------

    st.subheader("Charge Balance Correction")

    if st.button(
            "Auto Balance Water Analysis"
    ):

        if total_cation_meq > total_anion_meq:

            correction = (
                                 total_cation_meq -
                                 total_anion_meq
                         ) * 61

            corrected_hco3 = (
                    hco3 +
                    correction
            )

        else:

            correction = (
                                 total_anion_meq -
                                 total_cation_meq
                         ) * 61

            corrected_hco3 = max(
                0,
                hco3 - correction
            )

        st.session_state["corrected_hco3"] = corrected_hco3

        st.success(
            f"""
    Original HCO3 = {hco3:.2f} mg/L

    Suggested HCO3 = {corrected_hco3:.2f} mg/L
    """
        )
    ###############################################################################################

    # =================================================
    # SAVE VALUES FOR OTHER MODULES
    # =================================================

    st.session_state["calculated_tds"] = tds
    st.session_state["hardness"] = hardness
    st.session_state["conductivity"] = conductivity


    #####
    st.subheader("Water Summary")

    st.markdown("""
    <style>

    .kpi-card {
        background-color:#102a43;
        padding:15px;
        border-radius:10px;
        text-align:center;
        border:1px solid #1f4e79;
    }

    .kpi-title {
        font-size:14px;
        color:#a0c4ff;
        margin-bottom:8px;
    }

    .kpi-value {
        font-size:28px;
        font-weight:bold;
        color:white;
    }

    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">TDS (mg/L)</div>
            <div class="kpi-value">{tds:.1f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Hardness (mg/L)</div>
            <div class="kpi-value">{hardness:.1f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Conductivity (µS/cm)</div>
            <div class="kpi-value">{conductivity:.1f}</div>
        </div>
        """, unsafe_allow_html=True)

    c4, c5 = st.columns(2)

    with c4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Cations (meq/L)</div>
            <div class="kpi-value">{total_cation_meq:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c5:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Anions (meq/L)</div>
            <div class="kpi-value">{total_anion_meq:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    ###

    # =================================================
    # RESULTS
    # =================================================

    alkalinity = 0.0

    try:

        bicarbonate_row = df[
            df["Species"].astype(str).str.strip().str.upper()
            == "BICARBONATE"
            ]

        if not bicarbonate_row.empty:
            bicarbonate = float(
                bicarbonate_row.iloc[0]["Raw water"]
            )

            alkalinity = (
                                 hco3 * 50 / 61
                         ) + (
                                 co3 * 50 / 30
                         )

    except Exception:

        alkalinity = 0.0

    st.metric(
        "Alkalinity",
        f"{alkalinity:.1f} mg/L as CaCO3"
    )

    st.info(
        f"""
    Total Dissolved Solids : {tds:.1f} mg/L

    Hardness : {hardness:.1f} mg/L as CaCO3

    Conductivity : {conductivity:.1f} µS/cm

    Alkalinity : {alkalinity:.1f} mg/L as CaCO3
    """
    )
    #######################################################################################################


    ###########################################################################################################


    # =================================================
    # SAVE VALUES
    # =================================================

    st.session_state["uf_Turbidity"] = Turbidity
    st.session_state["uf_TSS"] = TSS
    st.session_state["uf_sdi"] = sdi
    st.session_state["uf_TOC"] = TOC
    st.session_state["alkalinity"] = alkalinity
    st.session_state["co3"] = co3



    # ==========================================
    # SAVE WATER CHEMISTRY FOR CEB/CIP
    # ==========================================

    st.session_state["raw_ph"] = ph

    st.session_state["bicarbonate"] = hco3

    st.session_state["carbonate"] = co3


    ####

    # =====================================================
    # EFFLUENT WATER
    # =====================================================

# =====================================================
# EFFLUENT WATER
# =====================================================


elif page == "Effluent Water":

    st.title("💧 UF Permeate Water Quality")

    # Feed Values

    feed_ca = st.session_state.get("ca", 0.0)
    feed_mg = st.session_state.get("mg", 0.0)
    feed_na = st.session_state.get("na", 0.0)
    feed_k = st.session_state.get("k", 0.0)

    feed_hco3 = st.session_state.get("hco3", 0.0)
    feed_co3 = st.session_state.get("co3", 0.0)

    feed_so4 = st.session_state.get("so4", 0.0)
    feed_cl = st.session_state.get("cl", 0.0)
    feed_no3 = st.session_state.get("no3", 0.0)

    feed_silica = st.session_state.get("silica", 0.0)
    feed_boron = st.session_state.get("boron", 0.0)

    feed_ph = st.session_state.get("feed_ph", 7.0)

    feed_tds = st.session_state.get("calculated_tds", 0.0)
    feed_hardness = st.session_state.get("hardness", 0.0)
    feed_conductivity = st.session_state.get("conductivity", 0.0)

    feed_Turbidity = st.session_state.get("Turbidity", 0.0)
    feed_TSS = st.session_state.get("TSS", 0.0)
    feed_TOC = st.session_state.get("TOC", 0.0)
    feed_sdi = st.session_state.get("sdi", 0.0)

    # UF Permeate

    uf_ca = feed_ca
    uf_mg = feed_mg
    uf_na = feed_na
    uf_k = feed_k

    uf_hco3 = feed_hco3
    uf_co3 = feed_co3

    uf_so4 = feed_so4
    uf_cl = feed_cl
    uf_no3 = feed_no3

    uf_silica = feed_silica
    uf_boron = feed_boron

    uf_ph = feed_ph

    uf_tds = feed_tds
    uf_hardness = feed_hardness
    uf_conductivity = feed_conductivity

    # Typical UF Removal Efficiencies

    uf_Turbidity = feed_Turbidity * 0.01
    uf_TSS = feed_TSS * 0.01
    uf_TOC = feed_TOC * 0.80

    if feed_sdi > 0:
        uf_sdi = 2.0
    else:
        uf_sdi = 0.0

    # Table

    effluent_df = pd.DataFrame({

        "Parameter": [
            "Calcium",
            "Magnesium",
            "Sodium",
            "Potassium",
            "Bicarbonate",
            "Carbonate",
            "Sulfate",
            "Chloride",
            "Nitrate",
            "Silica",
            "Boron",
            "TDS",
            "Hardness",
            "Conductivity",
            "Turbidity",
            "TSS",
            "TOC",
            "SDI",
            "pH"
        ],

        "Feed Water": [

            feed_ca,
            feed_mg,
            feed_na,
            feed_k,

            feed_hco3,
            feed_co3,

            feed_so4,
            feed_cl,
            feed_no3,

            feed_silica,
            feed_boron,

            feed_tds,
            feed_hardness,
            feed_conductivity,

            feed_Turbidity,
            feed_TSS,
            feed_TOC,
            feed_sdi,
            feed_ph
        ],

        "UF Permeate": [

            uf_ca,
            uf_mg,
            uf_na,
            uf_k,

            uf_hco3,
            uf_co3,

            uf_so4,
            uf_cl,
            uf_no3,

            uf_silica,
            uf_boron,

            uf_tds,
            uf_hardness,
            uf_conductivity,

            uf_Turbidity,
            uf_TSS,
            uf_TOC,
            uf_sdi,
            uf_ph
        ]
    })

    st.dataframe(
        effluent_df,
        use_container_width=True
    )

    # KPI Section

    st.markdown("### UF Removal Performance")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Turbidity",
            f"{uf_Turbidity:.3f} NTU",
            f"-{feed_Turbidity - uf_Turbidity:.2f}"
        )

    with c2:
        st.metric(
            "TSS",
            f"{uf_TSS:.3f} mg/L",
            f"-{feed_TSS - uf_TSS:.2f}"
        )

    with c3:
        st.metric(
            "TOC",
            f"{uf_TOC:.2f} mg/L",
            f"-{feed_TOC - uf_TOC:.2f}"
        )

    with c4:
        st.metric(
            "SDI",
            f"{uf_sdi:.1f}"
        )
#######################################################################################################

elif page == "Design":

    import math

    st.title("🔷 UF Design")

    # ======================================================
    # FEED FLOW
    # ======================================================

    left, right = st.columns([1, 2])

    with left:

        st.subheader("UF Feed Flow Rate")

        uf_feed_flow = st.number_input(
            "Automatic",
            value=st.session_state.get(
                "uf_feed_flow",
                50.0
            ),
            key="uf_feed_flow_design"
        )

        st.session_state["uf_feed_flow"] = uf_feed_flow

        # ======================================================
        # TECHNOLOGY
        # ======================================================

        st.subheader("UF technology Selection")

        technology_options = [
            "PVDF Out-In",
            "PES In-Out"
        ]

        uf_technology = st.selectbox(
            "UF technology",
            technology_options,
            index=technology_options.index(
                st.session_state.get(
                    "uf_technology_saved",
                    "PVDF Out-In"
                )
            )
        )

        st.session_state["uf_technology_saved"] = uf_technology

        st.session_state["uf_technology_saved"] = (
            st.session_state.get("uf_technology_saved")
        )

        # ======================================================
        # MODULE SELECTION PVDF out-in
        # ======================================================

        st.subheader("Module Selection")

        pvdf_module_data = {


            "IntegraTec XP 77 IP": {
                "area": 77,
                "length": 2491,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 13.98,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XP 77 IP IG": {
                "area": 77,
                "length": 2491,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 13.98,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XP 77": {
                "area": 77,
                "length": 2363,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 13.98,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XP 77 IG": {
                "area": 77,
                "length": 2363,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 13.98,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XP 51 IP": {
                "area": 51,
                "length": 1991,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 9.26,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XP 51 IP IG": {
                "area": 51,
                "length": 1991,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 9.26,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XP 51": {
                "area": 51,
                "length": 1863,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 9.26,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XP 51 IG": {
                "area": 51,
                "length": 1863,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 9.26,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XP 52 IC": {
                "area": 52,
                "length": 2265,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 9.44,
                "air_flow": 4.44,
                "cip_recycle": 4.40
            },

            "IntegraTec XP 55 UXA": {
                "area": 55,
                "length": 2332,
                "tmp": 0.7,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.7,

                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 9.98,
                "air_flow": 3.17,
                "cip_recycle": 6.60
            },

            "IntegraTec XTP 100 IG": {
                "area": 100,
                "length": 2363,
                "tmp": "N/A",
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.6,


                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 18.15,
                "air_flow": 7.61,
                "cip_recycle": 6.60
            },

            "IntegraTec XTP 100": {
                "area": 100,
                "length": 2363,
                "tmp": 0.6,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.6,


                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 18.15,
                "air_flow": 7.61,
                "cip_recycle": 6.60

            },

            "IntegraTec XTP 100 IP": {
                "area": 100,
                "length": 2491,
                "tmp": 0.6,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.6,


                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 18.15,
                "air_flow": 6.34,
                "cip_recycle": 6.60
            },

            "IntegraTec XTP 100 IP IG": {
                "area": 100,
                "length": 2491,
                "tmp": 0.6,
                "material": "PVDF",
                "mode": "Out-In",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.6,


                "flux_gfd": 41.23,
                "backwash_gfd": 58.9,
                "ceb_gfd": 58.9,
                "forward_flush": 18.15,
                "air_flow": 6.34,
                "cip_recycle": 6.60
            }

        }


        ########################################################################################

        # ======================================================
        # MODULE SELECTION PES in-out
        # ======================================================

        pes_module_data = {

            "Inge MB 0.9 XL 80 TR": {
                "area": 80,
                "length": 2101,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.9,


                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,
                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 8.81
            },

            "Inge MB 0.9 XL 60 TRs": {
                "area": 60,
                "length": 1879,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.9,
                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,
                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 6.60
            },

            "Inge MB 0.9 XL 80 OP": {
                "area": 80,
                "length": 1914,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.9,
                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,
                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 8.81
            },

            "Inge MB 0.9 XL 60 OP": {
                "area": 60,
                "length": 1679,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.9,
                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,
                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 6.60
            },

            "Inge MB 0.9 XL 38 OP": {
                "area": 38,
                "length": 1179,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.9,
                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,
                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 4.40
            },

            "Inge MB 0.9 L 55 V": {
                "area": 55,
                "length": 1898,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Open Platform",
                "orientation": "Vertical",
                "id": 0.9,
                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,
                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 6.16
            },

            "Inge MB 0.9 L 40 HB": {
                "area": 40,
                "length": 1527,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Open Platform",
                "orientation": "Horizontal",
                "id": 0.9,
                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,

                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 6.16
            },

            "Inge MB 0.9 L 55 H": {
                "area": 55,
                "length": 1538,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Open Platform",
                "orientation": "Horizontal",
                "id": 0.9,
                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,
                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 6.16
            },

            "Inge MB 0.9 XL 80 TR (Containerized)": {
                "area": 80,
                "length": 2101,
                "tmp": 1.0,
                "material": "PESm",
                "mode": "In-Out",
                "mounting": "Rack",
                "orientation": "Vertical",
                "id": 0.9,
                "flux_gfd": 44.18,
                "backwash_gfd": 135.474,
                "ceb_gfd": 70.682,
                "forward_flush": 0.0,
                "air_flow": 0.0,
                "cip_recycle": 8.81
            }

        }

        ##############################################################################

        if uf_technology == "PVDF Out-In":
            module_list = pvdf_module_data
        else:
            module_list = pes_module_data

        module_options = list(module_list.keys())

        saved_module = st.session_state.get(
            "uf_module_saved",
            module_options[0]
        )

        if saved_module not in module_options:
            saved_module = module_options[0]

        module = st.selectbox(
            "UF Module",
            module_options,
            index=module_options.index(saved_module)
        )

        st.session_state["uf_module_saved"] = module

        st.session_state["uf_module_saved"] = (
            st.session_state.get("uf_module_saved")
        )
        #################################################################################


        selected = module_list[module]
        st.session_state["selected_module_data"] = selected
        st.session_state["selected_module_name"] = module


        st.session_state["selected_module"] = module
        st.session_state["uf_module_area"] = selected["area"]
        st.session_state["uf_module_flux"] = selected["flux_gfd"]

        module_area = selected["area"]
        module_length = selected["length"]
        module_tmp = selected["tmp"]
        module_material = selected["material"]
        module_mode = selected["mode"]
        module_mounting = selected["mounting"]
        module_orientation = selected["orientation"]
        module_id = selected["id"]

#Display Details

        d1, d2, d3, d4 = st.columns(4)

        d1.metric("Module Area", f"{module_area} m²")
        d2.metric("Length", f"{module_length:,} mm")
        d3.metric("Max TMP", f"{module_tmp} bar")
        d4.metric("Fiber ID", f"{module_id} mm")

        st.info(
            f"""
        Material: {module_material}

        Mode: {module_mode}

        Mounting: {module_mounting}

        Orientation: {module_orientation}
        """
        )

    ####################################################################
    with right:

        c1, c2 = st.columns(2)

        with c1:
            flux_gfd = st.number_input(
                "Filtrate Flux (GFD)",
                min_value=10.0,
                max_value=80.0,
                value=float(selected["flux_gfd"])
            )

            flux = flux_gfd * 1.699

            backwash_gfd = st.number_input(
                "Backwash Flux (GFD)",
                value=float(selected["backwash_gfd"])
            )

            backwash_flux = backwash_gfd * 1.699

            ceb_gfd = st.number_input(
                "CEB Flux (GFD)",
                value=float(selected["ceb_gfd"])
            )

            ceb_flux = ceb_gfd * 1.699

            forward_flush = st.number_input(
                "Forward Flush Flow (gpm/module)",
                value=float(selected["forward_flush"])
            )

            air_flow = st.number_input(
                "Air Flow (scfm/module)",
                value=float(selected["air_flow"])
            )

        # Save both units
        st.session_state["uf_flux"] = flux
        st.session_state["uf_flux_gfd"] = flux_gfd

        st.session_state["uf_backwash_flux"] = backwash_flux
        st.session_state["uf_backwash_gfd"] = backwash_gfd

        st.session_state["uf_ceb_flux"] = ceb_flux
        st.session_state["uf_ceb_gfd"] = ceb_gfd



        with c2:
            feature = st.radio(
                "UF Special Features",
                [
                    "CEB only",
                    "mini-CIP only",
                    "CEB and mini-CIP"
                ]
            )

            adjust_chemicals = st.checkbox(
                "Adjust pH / Oxidant / Coagulant"
            )

            filtration_duration = st.number_input(
                "Filtration Duration (min)",
                value=25.0
            )

            acid_ceb = st.number_input(
                "Acid CEB Interval (hr)",
                value=168.0
            )

            alk_ceb = st.number_input(
                "Alkaline/Oxidant CEB Interval (hr)",
                value=24.0
            )

            cip_interval = st.number_input(
                "CIP Interval (days)",
                value=30.0
            )
    # ======================================================
    # AUTO CALCULATIONS
    # ======================================================

    required_area = (
                            uf_feed_flow * 1000
                    ) / flux

    required_modules = math.ceil(
        required_area / module_area
    )

    gross_permeate = (
                             required_area * flux
                     ) / 1000

    backwash_flow = (
                            required_area * backwash_flux
                    ) / 1000

    ceb_flow = (
                       required_area * ceb_flux
               ) / 1000
    # Save CEB Flow

    st.session_state["uf_ceb_flow"] = ceb_flow

    # ======================================================
    # SAVE VALUES
    # ======================================================

    st.session_state["uf_flux"] = flux
    st.session_state["uf_backwash_flux"] = backwash_flux
    st.session_state["uf_ceb_flux"] = ceb_flux
    st.session_state["uf_required_area"] = required_area
    st.session_state["uf_modules"] = required_modules
    st.session_state["uf_air_flow"] = air_flow
    st.session_state["uf_forward_flush"] = forward_flush
    st.session_state["uf_feature"] = feature
    st.session_state["uf_filtration_duration"] = filtration_duration
    st.session_state["uf_acid_ceb"] = acid_ceb
    st.session_state["uf_alk_ceb"] = alk_ceb
    st.session_state["uf_cip_interval"] = cip_interval

############################################################################################

elif page == "Configuration":



    import math

    st.title("⚙️ UF Configuration")

    # =====================================================
    # FETCH VALUES FROM DESIGN PAGE
    # =====================================================

    feed_flow = st.session_state.get(
        "uf_feed_flow",
        50.0
    )

    modules_required = st.session_state.get(
        "uf_modules",
        1
    )

    recovery = st.session_state.get(
        "uf_recovery",
        95.0
    )

    # =====================================================
    # USER CONFIGURATION
    # =====================================================

    left, right = st.columns(2)

    with left:

        st.subheader("Train Configuration")

        trains_online = st.number_input(
            "Operating Trains",
            min_value=1,
            key="trains_online"
        )

        standby_trains = st.number_input(
            "Standby Trains",
            min_value=0,
            key="standby_trains"
        )

        modules_per_train = math.ceil(
            modules_required / trains_online
        )

        total_trains = (
                trains_online +
                standby_trains
        )

    with right:

        st.subheader("Recovery & Cleaning")

        uf_recovery = st.number_input(
            "UF Recovery (%)",
            min_value=85.0,
            max_value=99.9,
            value=recovery
        )

        backwash_duration = st.number_input(
            "Backwash Duration (sec)",
            value=30
        )

        cip_duration = st.number_input(
            "CIP Duration (hr)",
            value=4
        )

    # =====================================================
    # CALCULATIONS
    # =====================================================

    gross_permeate = (
            feed_flow *
            uf_recovery /
            100
    )

    waste_flow = (
            feed_flow -
            gross_permeate
    )


    # =====================================================
    # CONFIGURATION TABLE
    # =====================================================


#System Configuration


    st.subheader("System Configuration")


    col1, col2 = st.columns([1, 1])

    with col1:

        standby_option = st.radio(
            "Standby Option",
            [
                "Constant operating flux, variable system output",
                "Constant system output, variable operating flux"
            ],
            key="standby_option"
        )

        storage_tank_option = st.selectbox(
            "Storage Tank Option",
            [
                "BW + Filtrate",
                "Filtrate Only",
                "No Tank"
            ]
        )

    with col2:


            st.text_input(
                "UF Module",
                value=st.session_state.get(
                    "uf_module",
                    ""
                ),
                disabled=True
            )


#Selected Configuration

    st.subheader("Selected Configuration")


    c1, c2, c3 = st.columns(3)

    with c1:
        racks_per_unit = st.number_input(
            "Racks/Unit",
            min_value=1,
            value=int(
                st.session_state.get(
                    "cfg_racks_per_unit_saved",
                    1
                )
            ),
            key="cfg_racks_per_unit"
        )

    with c2:
        modules_per_rack = st.number_input(
            "Modules/Rack",
            min_value=6,
            max_value=22,
            value=int(
                st.session_state.get(
                    "cfg_modules_per_rack_saved",
                    22
                )
            ),
            key="cfg_modules_per_rack"
        )


    with c3:
        total_racks = racks_per_unit * (
                st.session_state.get("online_units", 2) +
                st.session_state.get("standby_units", 0) +
                st.session_state.get("redundant_units", 1)
        )

        st.metric(
            "Total No. of Racks",
            total_racks
        )

        # ==========================================
        # BACKWASH & CIP FLOW CALCULATION
        # ==========================================

        module_data = st.session_state.get("selected_module_data", {})

        module_area = module_data.get("area", 77.0)
        backwash_gfd = module_data.get("backwash_gfd", 58.9)
        cip_recycle = module_data.get("cip_recycle", 6.6)

        # Current configuration
        modules_per_train = (
                racks_per_unit *
                modules_per_rack
        )

        # Convert GFD to LMH
        backwash_flux_lmh = 100.0

        # Train membrane area
        train_area = (
                modules_per_train *
                module_area
        )

        # Backwash Flow (m³/hr)
        backwash_flow = (
                                train_area *
                                backwash_flux_lmh
                        ) / 1000

        # CIP Flow (gpm)
        cip_flow_gpm = (
                modules_per_train *
                cip_recycle
        )

        # CIP Flow (m³/hr)
        cip_flow = (
                cip_flow_gpm *
                0.2271
        )

        # ==========================================
        # BACKWASH & CIP FLOW CALCULATION
        # ==========================================

        # =====================================================
        # SAVE VALUES
        # =====================================================

        st.session_state["uf_recovery"] = uf_recovery
        st.session_state["uf_trains_online"] = trains_online
        st.session_state["uf_trains_standby"] = standby_trains
        st.session_state["uf_modules_per_train"] = modules_per_train
        st.session_state["uf_backwash_flow"] = backwash_flow
        st.session_state["uf_cip_flow"] = cip_flow

        # =====================================================
        # SUMMARY
        # =====================================================

        st.markdown("---")
        st.subheader("UF Configuration Summary")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Operating Trains",
            trains_online
        )

        c2.metric(
            "Standby Trains",
            standby_trains
        )

        c3.metric(
            "Total Trains",
            total_trains
        )

        c4.metric(
            "Modules/Train",
            modules_per_train
        )


    #Unit Configuration

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        online_units = st.number_input(
            "Online Units",
            min_value=1,
            value=int(
                st.session_state.get(
                    "cfg_online_units_saved",
                    2
                )
            ),
            key="cfg_online_units"
        )

    with c2:
        standby_units = st.number_input(
            "Standby Units",
            min_value=0,
            value=int(
                st.session_state.get(
                    "cfg_standby_units_saved",
                    0
                )
            ),
            key="cfg_standby_units"
        )

    with c3:


        redundant_units = st.number_input(
            "redundant Units",
            min_value=0,
            value=int(
                st.session_state.get(
                    "cfg_redundant_units_saved",
                    1
                )
            ),
            key="cfg_redundant_units"
        )

    with c4:

        total_units = (
                online_units
                + standby_units
                + redundant_units
        )

        st.metric(
            "Total Units",
            total_units
        )

#Module Summary

    modules_per_unit = (
            racks_per_unit
            * modules_per_rack
    )


    total_modules = (
            total_units
            * modules_per_unit
    )

#########################################################################

# =====================================================
# Operating Flux
# =====================================================

# Feed Flow (m3/hr)
    flow_m3hr = st.session_state["uf_feed_flow"]

    # Convert m3/hr to GPM
    flow_gpm = flow_m3hr * 4.4029

# Module Area
    module_area_m2 = st.session_state["uf_module_area"]

    # Convert m2 to ft2
    module_area_ft2 = module_area_m2 * 10.764

    # Online Modules
    online_modules = (
            online_units *
            modules_per_unit
    )

    # Total Online Membrane Area
    total_area_ft2 = (
            online_modules *
            module_area_ft2
    )

    # Operating Flux (GFD)
    operating_flux_gfd = (
            flow_gpm * 1440
    ) / total_area_ft2


    #Display

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Modules/Unit",
            modules_per_unit
        )

    with c2:
        st.metric(
            "Total Modules",
            total_modules
        )

    with c3:
        st.metric(
            "Operating Flux",
            f"{operating_flux_gfd:.2f} gfd"
        )

    st.session_state["online_modules"] = online_modules

#Recommended Configurations

    required_modules = st.session_state.get(
        "uf_modules",
        1
    )

    import pandas as pd

    recommendations = []

    options = [
        (1, 18, 2),
        (2, 18, 1),
        (3, 12, 1),
        (6, 6, 1)
    ]

    for online, modules_rack, racks_unit in options:
        modules_unit = (
                modules_rack
                * racks_unit
        )

        online_modules = (
                online
                * modules_unit
        )

        recommendations.append([
            online,
            0,
            online,
            1,
            modules_rack,
            racks_unit,
            modules_unit,
            online_modules,
            online_modules
        ])




#Create DataFrame:

    config_df = pd.DataFrame(
        recommendations,
        columns=[
            "Online Units",
            "Standby Units",
            "Total Units",
            "Max Offline BW/CEB",
            "Modules/Rack",
            "Racks/Unit",
            "Modules/Unit",
            "Online Modules",
            "Total Modules"
        ]
    )

    st.dataframe(
        config_df,
        use_container_width=True
    )

#Recommended Rack Size Slider

    st.subheader("Recommended Configurations")

    rack_min, rack_max = st.select_slider(
        "IP Rack Size Limit",
        options=list(range(6, 23)),
        value=(6, 22)
    )

    st.write(
        f"Min IP Rack Size Limit : {rack_min}"
    )

    st.write(
        f"Max IP Rack Size Limit : {rack_max}"
    )

#Save to Session State



    st.session_state["online_modules"] = online_modules
    st.session_state["total_modules"] = total_modules
    st.session_state["operating_flux_gfd"] = operating_flux_gfd

##########################################################################################################################################################################
 #UF RECOVERY
  ########################################################################################################################################################
    # =====================================================
    # UF PERFORMANCE CALCULATION (WAVE STYLE)
    # =====================================================

    # Feed Flow
    feed_flow = st.session_state["uf_feed_flow"]  # m3/hr

    # Module Data
    module_data = st.session_state.get("selected_module_data", {})

    module_area_m2 = module_data.get("area", 77.0)
    cip_recycle = module_data.get("cip_recycle", 6.6)

    # -----------------------------------------------------
    # CONFIGURATION
    # -----------------------------------------------------

    online_trains = online_units

    modules_per_train = (
            racks_per_unit *
            modules_per_rack
    )

    online_modules = (
            online_trains *
            modules_per_train
    )

    # -----------------------------------------------------
    # MEMBRANE AREA
    # -----------------------------------------------------

    online_area_m2 = (
            online_modules *
            module_area_m2
    )

    online_area_ft2 = (
            online_area_m2 *
            10.764
    )

    # -----------------------------------------------------
    # GROSS FILTRATE
    # -----------------------------------------------------

    gross_permeate = (
                             operating_flux_gfd *
                             online_area_ft2 *
                             3.785
                     ) / 1000 / 24

    # m3/hr

    # -----------------------------------------------------
    # BACKWASH FLOW
    # -----------------------------------------------------

    # WAVE style BW flux
    backwash_flux_lmh = 100.0

    train_area = (
            modules_per_train *
            module_area_m2
    )

    backwash_flow = (
                            train_area *
                            backwash_flux_lmh
                    ) / 1000

    # m3/hr

    # -----------------------------------------------------
    # CIP FLOW
    # -----------------------------------------------------

    cip_flow_gpm = (
            modules_per_train *
            cip_recycle
    )

    cip_flow = (
            cip_flow_gpm *
            0.2271
    )

    # m3/hr

    # -----------------------------------------------------
    # BACKWASH LOSS
    # -----------------------------------------------------

    bw_duration_sec = 45

    bw_interval_min = 30

    bw_volume_cycle = (
                              backwash_flow *
                              bw_duration_sec
                      ) / 3600

    bw_loss_per_hr = (
            bw_volume_cycle *
            (60 / bw_interval_min)
    )

    # -----------------------------------------------------
    # FORWARD FLUSH LOSS
    # -----------------------------------------------------

    ff_duration_sec = 30

    ff_flow = backwash_flow

    ff_volume_cycle = (
                              ff_flow *
                              ff_duration_sec
                      ) / 3600

    ff_loss_per_hr = (
            ff_volume_cycle *
            (60 / bw_interval_min)
    )

    # -----------------------------------------------------
    # CEB LOSS
    # -----------------------------------------------------

    ceb_frequency_hr = 24

    ceb_duration_min = 10

    ceb_volume = (
                         backwash_flow *
                         ceb_duration_min
                 ) / 60

    ceb_loss_per_hr = (
            ceb_volume /
            ceb_frequency_hr
    )


    # -----------------------------------------------------
    # TOTAL WASTE
    # -----------------------------------------------------

    waste_flow = (
            bw_loss_per_hr +
            ff_loss_per_hr +
            ceb_loss_per_hr
    )

    # -----------------------------------------------------
    # NET FILTRATE
    # -----------------------------------------------------

    net_permeate = (
            gross_permeate -
            waste_flow
    )

    # -----------------------------------------------------
    # UF RECOVERY
    # -----------------------------------------------------

    uf_recovery = (
                          net_permeate /
                          feed_flow
                  ) * 100

    # Safety Limits
    uf_recovery = max(
        0,
        min(99.9, uf_recovery)
    )

    # -----------------------------------------------------
    # DISPLAY VALUES
    # -----------------------------------------------------
    c5, c6, c7, c8 = st.columns(4)

    c5.metric(
        "UF Recovery",
        f"{uf_recovery:.1f}%"
    )

    c6.metric(
        "Permeate Flow",
        f"{net_permeate:.1f} m³/hr"
    )

    c7.metric(
        "Backwash Flow",
        f"{backwash_flow:.1f} m³/hr"
    )

    c8.metric(
        "CIP Flow",
        f"{cip_flow:.1f} m³/hr"
    )


    ############################################################################################################################################################



    # =====================================================
    # SAVE CONFIGURATION
    # =====================================================

    if st.button(
        "💾 Save Configuration",
        key="save_configuration"
    ):

        st.session_state["cfg_racks_per_unit_saved"] = racks_per_unit
        st.session_state["cfg_modules_per_rack_saved"] = modules_per_rack
        st.session_state["cfg_online_units_saved"] = online_units
        st.session_state["cfg_standby_units_saved"] = standby_units
        st.session_state["cfg_redundant_units_saved"] = redundant_units

        st.session_state["cfg_storage_option_saved"] = (
            st.session_state.get("storage_option", "")
        )
        st.session_state["cfg_standby_option_saved"] = standby_option

        st.success("✅ Configuration Saved Successfully")

##########################################################################################
#BACKWASH
#####################################################################################

elif page == "Backwash":

    st.title("🔄 UF Backwash")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("Backwash Temperature")

        bw_temp = st.number_input(
            "Temperature (°F)",
            value=66.0,
            key="bw_temperature"
        )

        use_feed_temp = st.checkbox(
            "Use design temperature from feed water",
            value=True
        )

    with c2:
        st.subheader("Water Source")

        bw_source = st.selectbox(
            "Backwash Water Source",
            ["UF Filtrate", "RO Permeate (external)"],
            key="bw_source"
        )

        ff_source = st.selectbox(
            "Forward Flush Water Source",
            ["UF Filtrate", "RO Permeate (external)"],
            key="ff_source"
        )

    with c3:
        st.subheader("Backwash ProTOCol")

        proTOCol = st.selectbox(
            "ProTOCol",
            [
                "Normal ProTOCol",
                "Short ProTOCol"
            ],
            key="bw_proTOCol"
        )

    st.subheader("Backwash Oxidant")

    c1, c2, c3 = st.columns([1, 2, 1])

    with c1:
        oxidant_enabled = st.toggle(
            "Oxidant",
            key="oxidant_enabled"
        )

    with c2:
        oxidant_type = st.selectbox(
            "Chemical",
            [
                "Sodium Hypochlorite",
                "Hydrogen Peroxide",
                "Chloramine"
            ],
            disabled=not oxidant_enabled
        )

    with c3:
        oxidant_dose = st.number_input(
            "mg/L",
            value=0.0,
            disabled=not oxidant_enabled
        )
#############################
# DURATION
#############################

    st.subheader("Durations")

    d1, d2, d3, d4 = st.columns(4)

    with d1:

        filtrate_to_level = st.number_input(
            "Filtrate to Level (sec)",
            value=st.session_state.get(
                "bw_filtrate_to_level",
                0.0
            ),
            key="bw_filtrate_to_level_widget"
        )

        bottom_backwash = st.number_input(
            "Bottom Backwash (sec)",
            value=st.session_state.get(
                "bw_bottom_backwash",
                30.0
            ),
            key="bw_bottom_backwash_widget"
        )

    with d2:

        air_scour = st.number_input(
            "Air Scour (sec)",
            value=st.session_state.get(
                "bw_air_scour",
                20.0
            ),
            key="bw_air_scour_widget"
        )

        forward_flush = st.number_input(
            "Forward Flush (sec)",
            value=st.session_state.get(
                "bw_forward_flush",
                45.0
            ),
            key="bw_forward_flush_widget"
        )

    with d3:

        drain = st.number_input(
            "Drain (sec)",
            value=st.session_state.get(
                "bw_drain",
                30.0
            ),
            key="bw_drain_widget"
        )

        lumen_fill = st.number_input(
            "Lumen Fill (sec)",
            value=st.session_state.get(
                "bw_lumen_fill",
                0.0
            ),
            key="bw_lumen_fill_widget"
        )

    with d4:

        top_backwash = st.number_input(
            "Top Backwash (sec)",
            value=st.session_state.get(
                "bw_top_backwash",
                30.0
            ),
            key="bw_top_backwash_widget"
        )

        bw_between_air = st.number_input(
            "Backwashes Between Air Scour",
            value=st.session_state.get(
                "bw_between_air_scour",
                1
            ),
            key="bw_between_air_widget"
        )

    # =====================================================
    # SAVE BUTTON
    # =====================================================

    if st.button(
            "💾 Save Backwash Settings",
            key="save_backwash_settings"
    ):
        st.session_state["bw_filtrate_to_level"] = filtrate_to_level
        st.session_state["bw_bottom_backwash"] = bottom_backwash
        st.session_state["bw_air_scour"] = air_scour
        st.session_state["bw_forward_flush"] = forward_flush
        st.session_state["bw_drain"] = drain
        st.session_state["bw_lumen_fill"] = lumen_fill
        st.session_state["bw_top_backwash"] = top_backwash
        st.session_state["bw_between_air_scour"] = bw_between_air

        st.success("✅ Backwash settings saved")



# =====================================================
# CEB
# =====================================================

elif page == "CEB":

    st.title("🧪 UF CEB")

    # =====================================================
    # TOP SECTION
    # =====================================================

    c1, c2, c3 = st.columns(3)

    with c1:

        st.subheader("CEB Temperature")

        use_feed_temp = st.checkbox(
            "Use design temperature from feed water",
            value=True,
            key="ceb_use_feed_temp"
        )

        ceb_temp = st.number_input(
            "Temperature (°F)",
            value=66.0,
            key="ceb_temperature"
        )

    with c2:

        st.subheader("Water Source")

        ceb_water_source = st.selectbox(
            "CEB Water Source",
            [
                "UF Filtrate",
                "RO Permeate"
            ],
            key="ceb_water_source"
        )

    with c3:
        st.empty()

    # =====================================================
    # CHEMICAL SELECTION
    # =====================================================

    acid_col, alk_col, dis_col = st.columns(3)

    # -----------------------------------------------------
    # ACID CEB
    # -----------------------------------------------------

    with acid_col:

        st.subheader("Acid CEB")

        mineral_acid_enabled = st.toggle(
            "Mineral Acid",
            value=True,
            key="mineral_acid_enabled"
        )

        acid_type = st.selectbox(
            "Acid",
            [
                "HCl(32)",
                "H2SO4(98)",

            ],

            disabled=not mineral_acid_enabled,
            key="acid_type"
        )

        acid_ph = st.number_input(
            "Target pH",
            min_value=2.0,
            max_value=7.0,
            value=2.0,
            disabled=not mineral_acid_enabled,
            key="acid_ph"
        )

        organic_acid_enabled = st.toggle(
            "Organic Acid",
            value=False,
            key="organic_acid_enabled"
        )

        organic_acid = st.selectbox(
            "Organic Chemical",
            [
                "Citric Acid 100",
                "Oxalic Acid 100"
            ],
            disabled=not organic_acid_enabled,
            key="organic_acid"
        )

        if organic_acid == "Citric Acid 100":

            citric_dose = st.number_input(
                "Citric Acid Dose (mg/L)",
                value=20000.0,
                disabled=not organic_acid_enabled,
                key="citric_dose"
            )

        elif organic_acid == "Oxalic Acid 100":

            oxalic_dose = st.number_input(
                "Oxalic Acid Dose (mg/L)",
                value=10000.0,
                disabled=not organic_acid_enabled,
                key="oxalic_dose"
            )

    # =====================================================
    # CEB CHEMICAL CALCULATIONS
    # =====================================================

    st.markdown("---")
    st.subheader("CEB Chemical Consumption")

    # CEB Volume used for calculations

    ceb_volume_m3 = st.number_input(
        "CEB Solution Volume (m³)",
        value=5.0,
        min_value=0.1,
        key="ceb_volume_m3"
    )

    results = {}

    # =====================================================
    # ACID CEB DOSING
    # =====================================================

    if mineral_acid_enabled:

        if acid_ph <= 2:
            acid_dose_mgl = 500

        elif acid_ph <= 3:
            acid_dose_mgl = 250

        else:
            acid_dose_mgl = 100

        acid_mass_kg = (
                acid_dose_mgl
                * ceb_volume_m3
                / 1000
        )

        results["Acid Dose (mg/L)"] = acid_dose_mgl
        results["Pure Acid Required (kg)"] = round(
            acid_mass_kg,
            2
        )

        if acid_type == "HCl(32)":

            hcl_solution_kg = (
                    acid_mass_kg
                    / 0.32
            )

            results["HCl 32% Solution (kg)"] = round(
                hcl_solution_kg,
                2
            )

        elif acid_type == "H2SO4(93)":

            h2so4_solution_kg = (
                    acid_mass_kg
                    / 0.93
            )

            results["H2SO4 93% Solution (kg)"] = round(
                h2so4_solution_kg,
                2
            )


    # -----------------------------------------------------
    # ALKALI / OXIDANT CEB
    # -----------------------------------------------------

    with alk_col:

        st.subheader("Alkali/Oxidant CEB")

        alkali_enabled = st.toggle(
            "Alkali",
            value=True,
            key="alkali_enabled"
        )

        alkali_type = st.selectbox(
            "Alkali",
            [
                "NaOH(50)"

            ],
            disabled=not alkali_enabled,
            key="alkali_type"
        )

        alkali_ph = st.number_input(
            "Target pH ",
            min_value=7.0,
            max_value=12.0,
            value=12.0,
            disabled=not alkali_enabled,
            key="alkali_ph"
        )

        oxidant_enabled = st.toggle(
            "Oxidant",
            value=True,
            key="alkali_oxidant_enabled"
        )

        oxidant_type = st.selectbox(
            "Oxidant Type",
            [
                "NaOCl(12)"

            ],
            disabled=not oxidant_enabled,
            key="oxidant_type"
        )

        oxidant_dose = st.number_input(
            "Oxidant Dose (mg/L)",
            value=350.0,
            min_value=0.0,
            disabled=not oxidant_enabled,
            key="oxidant_dose"
        )

        lsi = st.number_input(
            "LSI",
            value=0.0,
            key="ceb_lsi"
        )

    # -----------------------------------------------------
    # DISINFECTION CEB
    # -----------------------------------------------------

    with dis_col:

        st.subheader("Disinfection CEB")

        disinfection_enabled = st.toggle(
            "Oxidant",
            value=False,
            key="disinfection_enabled"
        )

        disinfection_chemical = st.selectbox(
            "Chemical",
            [
                "NaOCl",
                "Chlorine Dioxide",
                "Peroxide"
            ],
            disabled=not disinfection_enabled,
            key="disinfection_chemical"
        )

        disinfection_dose = st.number_input(
            "Dose (mg/L)",
            value=0.0,
            disabled=not disinfection_enabled,
            key="disinfection_dose"
        )


        ################################################################################################################################################
        results = calculate_ceb_chemicals(

            ph=st.session_state.get(
                "feed_ph",
                7.0
            ),

            hco3=st.session_state.get(
                "hco3",
                0.0
            ),

            co3=st.session_state.get(
                "co3",
                0.0
            ),

            co2=st.session_state.get(
                "co2",
                0.0
            ),

            boron=st.session_state.get(
                "boron",
                0.0
            ),

            silica=st.session_state.get(
                "silica",
                0.0
            ),

            nh4=st.session_state.get(
                "ammonium",
                0.0
            ),

            temperature_c=st.session_state.get(
                "temperature",
                25.0
            )
        )
################################################################################
        # =====================================================
        # CHEMICAL FEED RATE (GAL/HR)
        # =====================================================

        def chemical_gph(
                flow_gpm,
                dose_mgl,
                strength,
                density
        ):
            flow_lph = (
                    flow_gpm *
                    3.78541 *
                    60
            )

            pure_kgph = (
                                dose_mgl *
                                flow_lph
                        ) / 1000000

            solution_kgph = (
                    pure_kgph /
                    strength
            )

            gph = (
                    solution_kgph /
                    density /
                    3.785
            )

            return gph


        # CEB Flow (m3/hr)

        ceb_flow_m3hr = st.session_state.get(
            "uf_ceb_flow",
            0
        )

        # Convert m3/hr to gpm

        ceb_flow_gpm = (
                ceb_flow_m3hr * 4.4029
        )

        # HCl Feed Rate

        acid_gph = chemical_gph(
            ceb_flow_gpm,
            results["hcl32_mgL"],
            0.32,
            1.16
        )
###########################################################################################################
        # NaOH Feed Rate

        alkali_gph = chemical_gph(
            ceb_flow_gpm,
            results["naoh50_mgL"],
            0.50,
            1.53
        )


        ###################################################################################################

        # NaOCl Feed Rate

        def naocl12_gph(flow_gpm, dose_mgl=350):
            flow_lph = flow_gpm * 3.78541 * 60

            available_cl2_kgph = (
                                         dose_mgl * flow_lph
                                 ) / 1_000_000

            naocl_solution_kgph = (
                    available_cl2_kgph / 0.12
            )

            density = 1.20

            gph = (
                    naocl_solution_kgph /
                    density /
                    3.785
            )

            return gph


        naocl_gph = naocl12_gph(746, 350)

        print(naocl_gph)


        # Save for Diagram

        st.session_state["acid_gph"] = acid_gph
        st.session_state["alkali_gph"] = alkali_gph
        st.session_state["naocl_gph"] = naocl_gph



        ##########################################################################
        c1, c2, c3 = st.columns(3)

        acid_gph = st.session_state.get(
            "acid_gph",
            0
        )

        alkali_gph = st.session_state.get(
            "alkali_gph",
            0
        )

        naocl_gph = st.session_state.get(
            "naocl_gph",
            0
        )


        with c1:
            st.metric(
                "HCl(32%)",
                f"{results['hcl32_mgL']:.0f} mg/L"
            )
            st.caption(
                f"{acid_gph:.1f} gal/h"
            )

        with c2:
            st.metric(
                "NaOH(50%)",
                f"{results['naoh50_mgL']:.0f} mg/L"
            )

            st.caption(
                f"{alkali_gph:.1f} gal/h"
            )

        with c3:
            st.metric(
                "NaOCl(12%)",
                f"{results['naocl12_mgL']:.0f} mg/L"
            )

            st.caption(
                f"{naocl_gph:.1f} gal/h"
            )

        st.write(
            f"Calculated Alkalinity: "
            f"{results['alkalinity']:.1f} mg/LL as CaCO3"
        )

        ################################################################################################################################
    # =====================================================
    # DURATION
    # =====================================================

    st.markdown("---")
    st.subheader("Duration")

    same_as_bw = st.checkbox(
        "Same as Backwash",
        key="ceb_same_as_backwash"
    )

    # If checked, load values from Backwash

    if same_as_bw:

        ceb_air_scour_default = st.session_state.get(
            "bw_air_scour",
            20.0
        )

        ceb_drain_default = st.session_state.get(
            "bw_drain",
            30.0
        )

        ceb_top_bw_default = st.session_state.get(
            "bw_top_backwash",
            30.0
        )

        ceb_bottom_bw_default = st.session_state.get(
            "bw_bottom_backwash",
            30.0
        )

        ceb_ff_default = st.session_state.get(
            "bw_forward_flush",
            45.0
        )

    else:

        ceb_air_scour_default = st.session_state.get(
            "ceb_air_scour",
            20.0
        )

        ceb_drain_default = st.session_state.get(
            "ceb_drain",
            30.0
        )

        ceb_top_bw_default = st.session_state.get(
            "ceb_top_bw",
            45.0
        )

        ceb_bottom_bw_default = st.session_state.get(
            "ceb_bottom_bw",
            45.0
        )

        ceb_ff_default = st.session_state.get(
            "ceb_forward_flush",
            45.0
        )

    # =====================================================
    # INPUTS
    # =====================================================

    d1, d2, d3, d4, d5 = st.columns(5)

    with d1:

        air_scour = st.number_input(
            "Air Scour (sec)",
            value=float(ceb_air_scour_default),
            key="ceb_air_scour_widget",
            disabled=same_as_bw
        )

        chemical_soak = st.number_input(
            "Chemical Soaking Duration (min)",
            value=float(
                st.session_state.get(
                    "chemical_soak",
                    10.0
                )
            ),
            key="chemical_soak_widget"
        )

    with d2:

        drain = st.number_input(
            "Drain (sec)",
            value=float(ceb_drain_default),
            key="ceb_drain_widget",
            disabled=same_as_bw
        )

        bw_rinse_drain_bottom = st.number_input(
            "BW Rinse Drain Bottom (sec)",
            value=float(
                st.session_state.get(
                    "bw_rinse_bottom",
                    0.0
                )
            ),
            key="bw_rinse_bottom_widget"
        )

    with d3:

        top_backwash = st.number_input(
            "Top Backwash (sec)",
            value=float(ceb_top_bw_default),
            key="ceb_top_bw_widget",
            disabled=same_as_bw
        )

        bw_rinse_drain_top = st.number_input(
            "BW Rinse Drain Top (sec)",
            value=float(
                st.session_state.get(
                    "bw_rinse_top",
                    0.0
                )
            ),
            key="bw_rinse_top_widget"
        )

    with d4:

        bottom_backwash = st.number_input(
            "Bottom Backwash (sec)",
            value=float(ceb_bottom_bw_default),
            key="ceb_bottom_bw_widget",
            disabled=same_as_bw
        )

    with d5:

        forward_flush = st.number_input(
            "Forward Flush (sec)",
            value=float(ceb_ff_default),
            key="ceb_forward_flush_widget",
            disabled=same_as_bw
        )

    # =====================================================
    # SAVE BUTTON
    # =====================================================

    if st.button(
            "💾 Save CEB Settings",
            key="save_ceb_settings"
    ):
        st.session_state["ceb_air_scour"] = air_scour
        st.session_state["ceb_drain"] = drain
        st.session_state["ceb_top_bw"] = top_backwash
        st.session_state["ceb_bottom_bw"] = bottom_backwash
        st.session_state["ceb_forward_flush"] = forward_flush

        st.session_state["chemical_soak"] = chemical_soak
        st.session_state["bw_rinse_bottom"] = bw_rinse_drain_bottom
        st.session_state["bw_rinse_top"] = bw_rinse_drain_top

        st.success("✅ CEB settings saved")

######################################################################################################
##############################################################################################
    # =====================================================
    # CEB CHEMICAL CONSUMPTION
    # =====================================================



###########################################################################################################
# CIP
##############################################################################################################


elif page == "CIP":

    st.title("🧪 UF CIP")

    # =====================================================
    # TOP SECTION
    # =====================================================

    c1, c2, c3 = st.columns(3)

    with c1:

        st.subheader("CIP Temperature")

        cip_temperature = st.number_input(
            "Recycle Temperature (°F)",
            min_value=66.0,
            max_value=104.0,
            value=95.0,
            key="cip_temperature"
        )

    with c2:

        st.subheader("Cycles")

        initial_bw_cycles = st.number_input(
            "Initial BW Cycles",
            min_value=1,
            max_value=10,
            value=2,
            key="cip_initial_bw_cycles"
        )

        rinse_soak_cycles = st.number_input(
            "Rinse/Soak Cycles",
            min_value=1,
            max_value=10,
            value=1,
            key="cip_rinse_soak_cycles"
        )

        rinse_bw_cycles = st.number_input(
            "Rinse BW Cycles",
            min_value=1,
            max_value=10,
            value=1,
            key="cip_rinse_bw_cycles"
        )

    with c3:

        st.subheader("Water Source")

        cip_water_source = st.selectbox(
            "CIP Water Source",
            [
                "UF Filtrate",
                "RO Permeate"

            ],
            key="cip_water_source"
        )


    # =====================================================
    # CHEMICALS
    # =====================================================

    acid_col, alk_col, surf_col = st.columns(3)

    # -----------------------------------------------------
    # ACID CIP
    # -----------------------------------------------------

    with acid_col:

        st.subheader("Acid CIP")

        mineral_acid_enabled = st.toggle(
            "Mineral Acid",
            value=True,
            key="cip_mineral_acid_enabled"
        )

        acid_type = st.selectbox(
            "Acid",
            [
                "HCl(32)",
                "H2SO4(98)"
            ],
            disabled=not mineral_acid_enabled,
            key="cip_acid_type"
        )

        acid_ph = st.number_input(
            "Target pH",
            min_value=2.0,
            max_value=7.0,
            value=2.0,
            disabled=not mineral_acid_enabled,
            key="cip_acid_ph"
        )

        organic_acid_enabled = st.toggle(
            "Organic Acid",
            value=False,
            key="cip_organic_acid_enabled"
        )

        organic_acid = st.selectbox(
            "Organic Acid",
            [
                "Citric Acid",
                "Oxalic Acid"
            ],
            disabled=not organic_acid_enabled,
            key="cip_organic_acid"
        )

        if organic_acid == "Citric Acid":

            organic_dose = st.number_input(
                "Citric Acid Dose (mg/L)",
                value=20000.0,
                disabled=not organic_acid_enabled,
                key="cip_citric_dose"
            )

        else:

            organic_dose = st.number_input(
                "Oxalic Acid Dose (mg/L)",
                value=10000.0,
                disabled=not organic_acid_enabled,
                key="cip_oxalic_dose"
            )

    # -----------------------------------------------------
    # ALKALI / OXIDANT CIP
    # -----------------------------------------------------

    with alk_col:

        st.subheader("Alkali/Oxidant CIP")

        alkali_enabled = st.toggle(
            "Alkali",
            value=True,
            key="cip_alkali_enabled"
        )

        alkali_type = st.selectbox(
            "Alkali",
            [
                "NaOH(50)"

            ],
            disabled=not alkali_enabled,
            key="cip_alkali_type"
        )

        alkali_ph = st.number_input(
            "Target pH",
            min_value=7.0,
            max_value=12.0,
            value=12.0,
            disabled=not alkali_enabled,
            key="cip_alkali_ph"
        )

        oxidant_enabled = st.toggle(
            "Oxidant",
            value=True,
            key="cip_oxidant_enabled"
        )

        oxidant_type = st.selectbox(
            "Oxidant",
            [
                "NaOCl(12)"

            ],
            disabled=not oxidant_enabled,
            key="cip_oxidant_type"
        )

        oxidant_dose = st.number_input(
            "Oxidant Dose (mg/L)",
            min_value=0.0,
            max_value=2500.0,
            value=2000.0,
            disabled=not oxidant_enabled,
            key="cip_oxidant_dose"
        )

        lsi = st.number_input(
            "LSI",
            value=0.0,
            key="cip_lsi"
        )


######################################################################################################################################
    # ------------------------------------------
    # =====================================================
    # SUMMARY
    # =====================================================

elif page == "Summary":

    st.title("📋 UltraPRO Summary")

    # =================================================
    # FEED WATER
    # =================================================

    st.subheader("Feed Water Quality")

    feed_df = pd.DataFrame({

        "Parameter": [
            "TDS",
            "Hardness",
            "Conductivity",
            "Alkalinity",
            "Turbidity",
            "TSS",
            "TOC",
            "SDI",
            "pH"
        ],

        "Value": [

            st.session_state.get("calculated_tds", 0),

            st.session_state.get("hardness", 0),

            st.session_state.get("conductivity", 0),

            st.session_state.get("alkalinity", 0),

            st.session_state.get("turbidity", 0),

            st.session_state.get("tss", 0),

            st.session_state.get("toc", 0),

            st.session_state.get("sdi", 0),

            st.session_state.get("feed_ph", 0)
        ]
    })

    st.dataframe(
        feed_df,
        use_container_width=True
    )

    # =================================================
    # UF PERMEATE
    # =================================================

    st.subheader("UF Permeate Quality")

    permeate_df = pd.DataFrame({

        "Parameter": [
            "TDS",
            "Hardness",
            "Conductivity",
            "Turbidity",
            "TSS",
            "TOC",
            "SDI",
            "pH"
        ],

        "Value": [

            st.session_state.get("ufp_tds", 0),

            st.session_state.get("ufp_hardness", 0),

            st.session_state.get("ufp_conductivity", 0),

            st.session_state.get("ufp_turbidity", 0),

            st.session_state.get("ufp_tss", 0),

            st.session_state.get("ufp_toc", 0),

            st.session_state.get("ufp_sdi", 0),

            st.session_state.get("ufp_ph", 0)
        ]
    })

    st.dataframe(
        permeate_df,
        use_container_width=True
    )

    # =================================================
    # UF DESIGN
    # =================================================

    st.subheader("UF Design Summary")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Feed Flow",
        f"{st.session_state.get('uf_feed_flow', 0):.1f} m³/hr"
    )

    c2.metric(
        "UF Modules",
        st.session_state.get("total_modules", 0)
    )

    c3.metric(
        "Operating Flux",
        f"{st.session_state.get('operating_flux_gfd', 0):.1f} gfd"
    )

    c4.metric(
        "Recovery",
        f"{st.session_state.get('uf_recovery', 0):.1f}%"
    )

    # =================================================
    # CONFIGURATION
    # =================================================

    st.subheader("Configuration")

    config_df = pd.DataFrame({

        "Item": [
            "Online Units",
            "Standby Units",
            "Redundant Units",
            "Racks/Unit",
            "Modules/Rack",
            "Total Modules"
        ],

        "Value": [

            st.session_state.get(
                "cfg_online_units_saved",
                0
            ),

            st.session_state.get(
                "cfg_standby_units_saved",
                0
            ),

            st.session_state.get(
                "cfg_redundant_units_saved",
                0
            ),

            st.session_state.get(
                "cfg_racks_per_unit_saved",
                0
            ),

            st.session_state.get(
                "cfg_modules_per_rack_saved",
                0
            ),

            st.session_state.get(
                "total_modules",
                0
            )
        ]
    })

    st.dataframe(
        config_df,
        use_container_width=True
    )

    # =================================================
    # PUMP SUMMARY
    # =================================================

    st.subheader("Pump Summary")

    p1, p2, p3 = st.columns(3)

    p1.metric(
        "Feed Pump",
        f"{st.session_state.get('feed_pump_psi', 0):.1f} psi"
    )

    p2.metric(
        "Backwash Pump",
        f"{st.session_state.get('backwash_pump_psi', 0):.1f} psi"
    )

    p3.metric(
        "CIP Pump",
        f"{st.session_state.get('cip_pump_psi', 0):.1f} psi"
    )

    # =================================================
    # BACKWASH
    # =================================================

    st.subheader("Backwash Summary")

    st.write(
        f"""
    Backwash Flow : {st.session_state.get('uf_backwash_flow', 0):.1f} m³/hr

    Air Scour : {st.session_state.get('bw_air_scour', 0)} sec

    Drain : {st.session_state.get('bw_drain', 0)} sec

    Forward Flush : {st.session_state.get('bw_forward_flush', 0)} sec
    """
    )

    # =================================================
    # CEB
    # =================================================

    st.subheader("CEB Chemical Summary")

    st.write(
        f"""
    HCl(32%) : {st.session_state.get('acid_dose_mgl', 0):.0f} mg/L

    HCl Feed Rate : {st.session_state.get('acid_gph', 0):.1f} gal/hr

    NaOH(50%) : {st.session_state.get('alkali_dose_mgl', 0):.0f} mg/L

    NaOH Feed Rate : {st.session_state.get('alkali_gph', 0):.1f} gal/hr

    NaOCl(12%) : {st.session_state.get('naocl_dose_mgl', 350):.0f} mg/L

    NaOCl Feed Rate : {st.session_state.get('naocl_gph', 0):.1f} gal/hr
    """
    )

    # =================================================
    # CIP
    # =================================================

    st.subheader("CIP Summary")

    st.write(
        f"""
    CIP Flow : {st.session_state.get('uf_cip_flow', 0):.1f} m³/hr

    CIP Interval : {st.session_state.get('uf_cip_interval', 0)} days
    """
    )
#REPORT
    st.markdown("---")

    b1, b2, b3 = st.columns(3)

    with b1:

        import json

        project_data = dict(st.session_state)

        project_json = json.dumps(
            project_data,
            indent=4,
            default=str
        )

        st.download_button(
            label="💾 Save Project",
            data=project_json,
            file_name="UltraPRO_Project.uff",
            mime="application/json"
        )

        uploaded_project = st.file_uploader(
            "Open Existing Project",
            type=["uff"]
        )

    with b2:

        def create_summary_pdf():
            buffer = BytesIO()

            pdf = canvas.Canvas(buffer)

            y = 800

            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(
                50,
                y,
                "UltraPRO UF Design Report"
            )

            y -= 40

            pdf.setFont("Helvetica", 10)

            pdf.drawString(
                50,
                y,
                f"Feed Flow : {st.session_state.get('uf_feed_flow', 0):.1f} m3/hr"
            )

            y -= 20

            pdf.drawString(
                50,
                y,
                f"UF Module : {st.session_state.get('selected_module', '')}"
            )

            y -= 20

            pdf.drawString(
                50,
                y,
                f"Total Modules : {st.session_state.get('total_modules', 0)}"
            )

            y -= 20

            pdf.drawString(
                50,
                y,
                f"Operating Flux : {st.session_state.get('operating_flux_gfd', 0):.1f} GFD"
            )

            y -= 20

            pdf.drawString(
                50,
                y,
                f"Recovery : {st.session_state.get('uf_recovery', 0):.1f}%"
            )

            y -= 20

            pdf.drawString(
                50,
                y,
                f"Backwash Flow : {st.session_state.get('uf_backwash_flow', 0):.1f} m3/hr"
            )

            y -= 20

            pdf.drawString(
                50,
                y,
                f"CIP Flow : {st.session_state.get('uf_cip_flow', 0):.1f} m3/hr"
            )

            y -= 40

            pdf.drawString(
                50,
                y,
                f"HCl(32%) : {st.session_state.get('acid_dose_mgl', 0):.0f} mg/L"
            )

            y -= 20

            pdf.drawString(
                50,
                y,
                f"NaOH(50%) : {st.session_state.get('alkali_dose_mgl', 0):.0f} mg/L"
            )

            y -= 20

            pdf.drawString(
                50,
                y,
                f"NaOCl(12%) : {st.session_state.get('naocl_dose_mgl', 350):.0f} mg/L"
            )

            pdf.save()

            buffer.seek(0)

            return buffer


        pdf_file = create_summary_pdf()

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_file,
            file_name="UltraPRO_Report.pdf",
            mime="application/pdf"
        )


#Additional setting

    # =====================================================
    # ADDITIONAL SETTINGS
    # =====================================================

elif page == "Additional Settings":

    st.title("⚙️ Additional Settings")

    c1, c2, c3 = st.columns(
        [5, 5, 5],
        gap="small"
    )

    # =====================================================
    # PRESSURE
    # =====================================================

    with c1:

        st.subheader("Pressure")



        avg_air_pressure = st.number_input(
            "Average Air Scour Pressure (psi)",
            value=float(st.session_state.get("avg_air_pressure_saved", 7.25)),
            key="avg_air_pressure"
        )

        max_air_pressure = st.number_input(
            "Maximum Process Air Pressure (psi)",
            value=float(st.session_state.get("max_air_pressure_saved", 0.0)),
            key="max_air_pressure"
        )

        filtrate_pressure = st.number_input(
            "Filtrate Pressure (psi)",
            value=float(st.session_state.get("filtrate_pressure_saved", 0.0)),
            key="filtrate_pressure"
        )

        filtration_piping_dp = st.number_input(
            "Filtration Piping Pressure Drop (psi)",
            value=float(st.session_state.get("filtration_piping_dp_saved", 1.45)),
            key="filtration_piping_dp"
        )

        strainer_dp = st.number_input(
            "Strainer Pressure Drop (psi)",
            value=float(st.session_state.get("strainer_dp_saved", 0.0)),
            key="strainer_dp"
        )

        bw_piping_dp = st.number_input(
            "Backwash Piping Pressure Drop (psi)",
            value=float(st.session_state.get("bw_piping_dp_saved", 4.35)),
            key="bw_piping_dp"
        )

        cip_piping_dp = st.number_input(
            "CIP Piping Pressure Drop (psi)",
            value=float(st.session_state.get("cip_piping_dp_saved", 21.76)),
            key="cip_piping_dp"
        )

    # =====================================================
    # STORAGE PARAMETERS
    # =====================================================

    with c2:

        st.subheader("Tank Storage Parameters")

        chemical_storage_time = st.number_input(
            "Chemical Storage Time (Days)",
            value=float(st.session_state.get("chemical_storage_time_saved", 30.0)),
            key="chemical_storage_time"
        )

        bw_refill_rate = st.number_input(
            "Backwash Only Tank Refill Rate (% of filtrate)",
            value=float(st.session_state.get("bw_refill_rate_saved", 0.0)),
            key="bw_refill_rate"
        )

        st.markdown("---")

        st.subheader("Tank Size Factor")

        bw_filtrate_factor = st.number_input(
            "BW + Filtrate Tank (%)",
            value=float(st.session_state.get("bw_filtrate_factor_saved", 100.0)),
            key="bw_filtrate_factor"
        )

        bw_only_factor = st.number_input(
            "BW Only Tank (%)",
            value=float(st.session_state.get("bw_only_factor_saved", 100.0)),
            key="bw_only_factor"
        )

        cip_tank_factor = st.number_input(
            "CIP Tank (% of module volume)",
            value=float(st.session_state.get("cip_tank_factor_saved", 200.0)),
            key="cip_tank_factor"
        )

        st.markdown("---")

        st.subheader("Strainer Specification")

        strainer_recovery = st.number_input(
            "Strainer Recovery (%)",
            value=float(st.session_state.get("strainer_recovery_saved", 100.0)),
            key="strainer_recovery"
        )

        strainer_size = st.number_input(
            "Strainer Size (µm)",
            value=float(st.session_state.get("strainer_size_saved", 150.0)),
            key="strainer_size"
        )

        st.markdown("---")

        st.subheader("UF Organics Rejection")

        TOC_rejection = st.number_input(
            "TOC Rejection (%)",
            value=float(st.session_state.get("TOC_rejection_saved", 0.0)),
            key="TOC_rejection"
        )

    # =====================================================
    # POWER / TIMINGS
    # =====================================================

    with c3:

        st.subheader("Power")

        plc_power = st.number_input(
            "PLC Power Requirement per Train (hp)",
            value=float(st.session_state.get("plc_power_saved", 0.09)),
            key="plc_power"
        )

        valve_power = st.number_input(
            "Valve Power Requirement per Valve (hp)",
            value=float(st.session_state.get("valve_power_saved", 0.0)),
            key="valve_power"
        )

        st.markdown("---")

        st.subheader("Miscellaneous Timings")

        valves_per_unit = st.number_input(
            "Valves per Unit",
            value=int(st.session_state.get("valves_per_unit_saved", 6)),
            key="valves_per_unit"
        )

        valve_open_close = st.number_input(
            "Valve Open/Close Action Duration (sec)",
            value=float(st.session_state.get("valve_open_close_saved", 5.0)),
            key="valve_open_close"
        )

        typical_wait = st.number_input(
            "Typical Wait Duration (sec)",
            value=float(st.session_state.get("typical_wait_saved", 0.0)),
            key="typical_wait"
        )

        pump_ramp = st.number_input(
            "Typical Pump Ramp (sec)",
            value=float(st.session_state.get("pump_ramp_saved", 0.0)),
            key="pump_ramp"
        )

    # =====================================================
    # TMP INCREASE
    # =====================================================

    st.markdown("---")
    st.subheader("Filtration TMP Increase Between Processes")

    t1, t2, t3, t4, t5 = st.columns(5)

    with t1:
        bw_tmp = st.number_input(
            "Backwash",
            value=float(st.session_state.get("bw_tmp_saved", 0.0)),
            key="bw_tmp"
        )

    with t2:
        acid_ceb_tmp = st.number_input(
            "Acid CEB",
            value=float(st.session_state.get("acid_ceb_tmp_saved", 0.0)),
            key="acid_ceb_tmp"
        )

    with t3:
        mini_cip_tmp = st.number_input(
            "Mini-CIP",
            value=float(st.session_state.get("mini_cip_tmp_saved", 0.0)),
            key="mini_cip_tmp"
        )

    with t4:
        alk_ceb_tmp = st.number_input(
            "Alkali CEB",
            value=float(st.session_state.get("alk_ceb_tmp_saved", 0.0)),
            key="alk_ceb_tmp"
        )

    with t5:
        cip_tmp = st.number_input(
            "CIP",
            value=float(st.session_state.get("cip_tmp_saved", 0.0)),
            key="cip_tmp"
        )


###########################################################################################################################
        # =====================================================
        # PUMP PRESSURES
        # =====================================================

        # Feed Pump

        feed_tmp = st.number_input(
            "Feed TMP (psi)",
            value=float(
                st.session_state.get(
                    "feed_tmp_saved",
                    8.0
                )
            ),
            key="feed_tmp"
        )

        feed_pump_psi = (
                feed_tmp
                + filtration_piping_dp
                + strainer_dp
                + filtrate_pressure
        )

        feed_head_ft = (
                feed_pump_psi * 2.31
        )
#Backwash Pump

        bw_module_pressure = st.number_input(
            "Backwash Module Pressure (psi)",
            value=float(
                st.session_state.get(
                    "bw_module_pressure_saved",
                    10.0
                )
            ),
            key="bw_module_pressure"
        )

        backwash_pump_psi = (
                bw_module_pressure
                + bw_piping_dp
        )
#CIP Pump

        bw_head_ft = (
                backwash_pump_psi * 2.31
        )

        cip_module_pressure = st.number_input(
            "CIP Module Pressure (psi)",
            value=float(
                st.session_state.get(
                    "cip_module_pressure_saved",
                    5.0
                )
            ),
            key="cip_module_pressure"
        )

        cip_pump_psi = (
                cip_module_pressure
                + cip_piping_dp
        )

        cip_head_ft = (
                cip_pump_psi * 2.31
        )

#Pump Flow

        feed_flow_gpm = (
                st.session_state["uf_feed_flow"]
                * 4.4029
        )

        bw_flow_gpm = (
                st.session_state.get(
                    "uf_backwash_flow",
                    0
                ) * 4.4029
        )

        cip_flow_gpm = (
                st.session_state.get(
                    "uf_cip_flow",
                    0
                ) * 4.4029
        )

#Pump Power

        pump_efficiency = 0.70

        feed_hp = (
                          feed_flow_gpm
                          * feed_head_ft
                  ) / (
                          3960 * pump_efficiency
                  )

        bw_hp = (
                        bw_flow_gpm
                        * bw_head_ft
                ) / (
                        3960 * pump_efficiency
                )

        cip_hp = (
                         cip_flow_gpm
                         * cip_head_ft
                 ) / (
                         3960 * pump_efficiency
                 )




#DISPLAY

    st.subheader("Pump Sizing Summary")

    left, center, right = st.columns([1,1,1], gap="small")

    with left:
        st.markdown(
            f"""
            <div style="
                padding:15px;
                border:1px solid #1f4e79;
                border-radius:10px;
                text-align:center;
            ">
                <h3>Feed Pump</h3>
                <h1>{feed_pump_psi:.1f} psi</h1>
                <h4>{feed_head_ft:.1f} ft</h4>
                <h4>{feed_hp:.2f} hp</h4>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.caption(
            f"{feed_head_ft:.1f} ft | {feed_hp:.2f} hp"
        )

    with center:

        st.markdown(
            f"""
            <div style="
                padding:15px;
                border:1px solid #1f4e79;
                border-radius:10px;
                text-align:center;
            ">
                <h3>Backwash Pump</h3>
                <h1>{backwash_pump_psi:.1f} psi</h1>
                <h4>{bw_head_ft:.1f} ft</h4>
                <h4>{bw_hp:.2f} hp</h4>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.caption(
            f"{bw_head_ft:.1f} ft | {bw_hp:.2f} hp"
        )

    with right:

        st.markdown(
            f"""
                            <div style="
                                padding:15px;
                                border:1px solid #1f4e79;
                                border-radius:10px;
                                text-align:center;
                            ">
                                <h3>Feed Pump</h3>
                                <h1>{cip_pump_psi:.1f} psi</h1>
                                <h4>{cip_head_ft:.1f} ft</h4>
                                <h4>{cip_hp:.2f} hp</h4>
                            </div>
                            """,
            unsafe_allow_html=True
        )

        st.caption(
            f"{cip_head_ft:.1f} ft | {cip_hp:.2f} hp"
        )


    # =====================================================
    # SAVE BUTTON
    # =====================================================

    if st.button(
            "💾 Save Additional Settings",
            key="save_additional_settings"
    ):
        # Pressure
        st.session_state["avg_air_pressure_saved"] = avg_air_pressure
        st.session_state["max_air_pressure_saved"] = max_air_pressure
        st.session_state["filtrate_pressure_saved"] = filtrate_pressure
        st.session_state["filtration_piping_dp_saved"] = filtration_piping_dp
        st.session_state["strainer_dp_saved"] = strainer_dp
        st.session_state["bw_piping_dp_saved"] = bw_piping_dp
        st.session_state["cip_piping_dp_saved"] = cip_piping_dp

        # Storage
        st.session_state["chemical_storage_time_saved"] = chemical_storage_time
        st.session_state["bw_refill_rate_saved"] = bw_refill_rate

        # Tank Factors
        st.session_state["bw_filtrate_factor_saved"] = bw_filtrate_factor
        st.session_state["bw_only_factor_saved"] = bw_only_factor
        st.session_state["cip_tank_factor_saved"] = cip_tank_factor

        # Strainer
        st.session_state["strainer_recovery_saved"] = strainer_recovery
        st.session_state["strainer_size_saved"] = strainer_size

        # Organics
        st.session_state["TOC_rejection_saved"] = TOC_rejection

        # Power
        st.session_state["plc_power_saved"] = plc_power
        st.session_state["valve_power_saved"] = valve_power

        # Misc
        st.session_state["valves_per_unit_saved"] = valves_per_unit
        st.session_state["valve_open_close_saved"] = valve_open_close
        st.session_state["typical_wait_saved"] = typical_wait
        st.session_state["pump_ramp_saved"] = pump_ramp

        # TMP
        st.session_state["bw_tmp_saved"] = bw_tmp
        st.session_state["acid_ceb_tmp_saved"] = acid_ceb_tmp
        st.session_state["mini_cip_tmp_saved"] = mini_cip_tmp
        st.session_state["alk_ceb_tmp_saved"] = alk_ceb_tmp
        st.session_state["cip_tmp_saved"] = cip_tmp

        st.session_state["feed_tmp_saved"] = feed_tmp

        st.session_state["bw_module_pressure_saved"] = (
            bw_module_pressure
        )

        st.session_state["cip_module_pressure_saved"] = (
            cip_module_pressure
        )

        st.session_state["feed_pump_head_ft"] = feed_head_ft
        st.session_state["bw_pump_head_ft"] = bw_head_ft
        st.session_state["cip_pump_head_ft"] = cip_head_ft

        st.session_state["feed_pump_hp"] = feed_hp
        st.session_state["bw_pump_hp"] = bw_hp
        st.session_state["cip_pump_hp"] = cip_hp

        st.success("✅ Additional Settings Saved Successfully")

##############################

        ############################################################################################


######################################################################################################################
#NOTES

#Dosing requirement for CEB HCL
#How much acid is needed to reduce the  CEB solution from its starting pH to pH 2.This depends heavily on: Alkalinity

#Dosing requirement for CEB NAOH :
#The amount of NaOH required depends on:Alkalinity, Dissolved CO2, Existing pH, Bicarbonate concentration
#Alkalinity = 20 mg/L as CaCO3 require 150-250 mg/L HCl
#High alkalinity water:Alkalinity = 250 mg/L as CaCO3 require:700-1000 mg/L HCl
#
#The reason the Backwash Pump flow does not change when feed flow changes is that most UF design software calculates backwash flow from the installed
# membrane area (or number of modules), not from plant feed flow. Area (no of modulex area of one module)/Backwash flux

#HCl(32) to achieve pH 2
#NaOH(50) to achieve pH 12
#NaOCl(12) fixed at 350 mg/L
#Uses alkalinity calculated from Feed Water page
#Calculates chemical dose (mg/L) and pump rate (gal/h)

#Wave determines how much:

#H⁺ (from HCl) is required to drive carbonate species to pH 2
#OH⁻ (from NaOH) is required to drive carbonate species to pH 12

#Acid and alkali dose are controlled mainly by the carbonate buffering system
#of the water, not by pH alone. To determine the HCl dose required to reduce
#water from pH 7.4 to pH 2.0, the calculation first converts bicarbonate (HCO₃⁻)
 #and carbonate (CO₃²⁻) into alkalinity (acid-neutralizing capacity), then computes
#the hydrogen ions (H⁺) needed to (1) neutralize the alkalinity by converting
 #HCO₃⁻ and CO₃²⁻ into CO₂ and water, and (2) further increase the free hydrogen
 #ion concentration until the final solution reaches pH 2.0. Similarly, to achieve
 #pH 12.0, NaOH demand is calculated by determining the hydroxide ions (OH⁻)
 #required to overcome the carbonate buffering system and raise the equilibrium
#to the target pH. Therefore, the required HCl or NaOH dosage depends on feed-water
#alkalinity, bicarbonate, carbonate, dissolved CO₂, temperature, and initial pH.
#In most natural waters, higher alkalinity means more acid is required to reach pH 2 and
 #more caustic is required to reach pH 12. Professional software such as WAVE uses
 #carbonate-speciation equations (K₁ and K₂ equilibrium constants) and alkalinity
 #balance calculations to determine the actual HCl(32%) and NaOH(50%) dosages,
 #rather than using fixed values or pH alone.

 #BUFFERING + PH CHANGE

 #CO3-- + H+ → HCO3->>>>>>>>>>HCO3- + H+ → H2CO3>>>>>>>>>>>>>>>H2CO3 → CO2 + H2O
 #CO3--
                        #↓
                        #HCO3-
                        #↓
                        #H2CO3
                        #↓
                        #CO2
                        #↓
                        #Free H+

#CO2 + OH- → HCO3->>>>>>>>>>>>>>>HCO3- + OH- → CO3-- + H2O>>>>>>>OH- remains free

                  #  CO2
                  #  ↓
                  #  HCO3 -
                   # ↓
                   # CO3 - -
                  #  ↓
                  #  Free
                  # OH -#

        #Low pH  → Removes inorganic fouling
        # High pH → Removes organic fouling
        #Oxidant → Removes biological fouling

       # if water_type == "Surface Water":
           # default_flux = 28  # GFD

       # elif water_type == "Municipal Water":
           # default_flux = 35  # GFD

       # elif water_type == "Ground Water":
            #default_flux = 45  # GFD

       # elif water_type == "UF Permeate":
           # default_flux = 60  # GFD

#CEB
 #Acid CIP Citric Acid (50%) or HCl (32%): inorganic fouling (scale and metal deposits) for CaCO3 scaling/ Iron fouling/ Manganese fouling/ Metal oxides
#Alkaline CIP NaOH (50%): for Organic fouling/ Biofouling/ Natural Organics-

##1. Organic Fouling Organic fouling is deposition of dissolved or colloidal organic matter on the membrane surface.Humic acids/// Fulvic acids/ Decaying vegetation
# Algae by-products/ Industrial organics


#2. Biofouling : Biofouling occurs when microorganisms grow on the membrane surface and form a biofilm.Bacteria /Fungi /Microbial slime /Algae.
# The microorganisms produce:  EPS (Extracellular Polymeric Substances) which creates a sticky layer that's difficult to remove.


#NAOH loosens the slime layer


#Oxidant CIP NaOCl (12%): for Biological fouling/ Microbial slime

#NaOCl kills the microorganisms

 ####1. Feed Pump

          #  The feed pump must overcome:

        #
          #  TMP (Transmembrane Pressure)
           # + Piping Losses
          #  + Strainer Losses
          #  + Elevation Difference
          #  + Safety Margin


########2. Backwash Pump

           # This is typically the largest UF pump.

            #The backwash pump must overcome:

           # Module Backwash Pressure+
            #+ Backwash Piping Loss
            #+ Strainer Loss
           # + Elevation
#####CIP Pump
            #Modules
            #+
            #Piping
           # +
            #Tank loop


#CIP (Clean-In-Place) Every 1-6 months/ when TMP increase > 30-50%, Permeability loss > 10-15%
#CEB Every 6-24 hours/
