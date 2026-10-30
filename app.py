
import streamlit as st
import qrcode
import csv
import io
import zipfile
import re

from PIL import Image, ImageDraw
from qrcode.constants import ERROR_CORRECT_H
from qrcode.image.svg import SvgPathImage


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="QR Code Studio Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================
# CUSTOM DESIGN
# =====================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: linear-gradient(135deg, #07111f, #0b1930, #101e38);
    color: #f4f7ff;
}

section[data-testid="stSidebar"] {
    background: #081426;
    border-right: 1px solid #203653;
}

h1 {
    color: #8bc5ff !important;
    font-weight: 800 !important;
}

h2, h3 {
    color: #d7eaff !important;
}

p, label {
    color: #c5d5e9;
}

div.stButton > button,
div.stDownloadButton > button {
    background: linear-gradient(90deg, #087cff, #6845ff);
    color: white;
    border: 0;
    border-radius: 10px;
    font-weight: 700;
    min-height: 43px;
    transition: 0.2s;
}

div.stButton > button:hover,
div.stDownloadButton > button:hover {
    border: 1px solid #91caff;
    color: white;
}

div[data-testid="stMetric"] {
    background: #11233d;
    padding: 17px;
    border: 1px solid #263f60;
    border-radius: 12px;
}

div[data-testid="stForm"] {
    background: #0d1c31;
    padding: 18px;
    border: 1px solid #243d5b;
    border-radius: 14px;
}

hr {
    border-color: #29415e;
}

.small-note {
    color: #8fa9c7;
    font-size: 13px;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# SESSION STATE
# =====================================================

if "history" not in st.session_state:
    st.session_state.history = []

if "current_qr" not in st.session_state:
    st.session_state.current_qr = None


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def build_payload(qr_type, values):

    if qr_type == "Website URL":
        url = values["url"].strip()

        if not re.match(r"^https?://", url, re.I):
            raise ValueError("URL must start with http:// or https://")

        return url

    elif qr_type == "Plain Text":
        return values["text"].strip()

    elif qr_type == "Email":
        email = values["email"].strip()

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValueError("Enter a valid email address.")

        return "mailto:" + email

    elif qr_type == "Phone Number":
        phone = values["phone"].strip()
        cleaned = re.sub(r"[\s()+-]", "", phone)

        if not re.fullmatch(r"\d{7,15}", cleaned):
            raise ValueError("Enter a valid phone number.")

        return "tel:" + phone

    elif qr_type == "SMS":
        phone = values["sms_phone"].strip()
        message = values["sms_message"].strip()

        if not re.fullmatch(r"\+?\d{7,15}", phone.replace(" ", "")):
            raise ValueError("Enter a valid phone number.")

        return f"SMSTO:{phone}:{message}"

    elif qr_type == "Wi-Fi":
        ssid = values["ssid"].strip()
        password = values["wifi_password"]
        security = values["security"]

        if not ssid:
            raise ValueError("Enter your Wi-Fi network name.")

        if security != "nopass" and not password:
            raise ValueError("Enter the Wi-Fi password.")

        def escape_wifi(value):
            return (value.replace("\\", "\\\\")
                         .replace(";", "\\;")
                         .replace(",", "\\,")
                         .replace(":", "\\:")
                         .replace('"', '\\"'))

        return (
            f'WIFI:T:{security};'
            f'S:{escape_wifi(ssid)};'
            f'P:{escape_wifi(password)};;'
        )

    elif qr_type == "vCard":
        name = values["name"].strip()
        phone = values["card_phone"].strip()
        email = values["card_email"].strip()

        if not name:
            raise ValueError("Enter a contact name.")

        return (
            "BEGIN:VCARD\n"
            "VERSION:3.0\n"
            f"FN:{name}\n"
            f"TEL:{phone}\n"
            f"EMAIL:{email}\n"
            "END:VCARD"
        )


def make_qr(data, foreground, background, size, border, logo=None):

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=size,
        border=border
    )

    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color=foreground,
        back_color=background
    ).convert("RGB")

    if logo is not None:

        logo_image = Image.open(logo).convert("RGBA")

        qr_width, qr_height = image.size

        logo_size = int(qr_width * 0.20)

        logo_image.thumbnail((logo_size, logo_size))

        logo_width, logo_height = logo_image.size

        center_x = qr_width // 2
        center_y = qr_height // 2

        padding = max(8, qr_width // 45)

        backing_size = max(logo_width, logo_height) + padding * 2

        backing = Image.new(
            "RGBA",
            (backing_size, backing_size),
            "white"
        )

        draw = ImageDraw.Draw(backing)

        draw.rounded_rectangle(
            (0, 0, backing_size - 1, backing_size - 1),
            radius=12,
            fill="white"
        )

        backing.alpha_composite(
            logo_image,
            (
                (backing_size - logo_width) // 2,
                (backing_size - logo_height) // 2
            )
        )

        image = image.convert("RGBA")

        image.alpha_composite(
            backing,
            (
                center_x - backing_size // 2,
                center_y - backing_size // 2
            )
        )

        image = image.convert("RGB")

    return image


def image_to_bytes(image):

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_svg(data, foreground, background, border):

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=border
    )

    qr.add_data(data)
    qr.make(fit=True)

    image = qr.make_image(
        image_factory=SvgPathImage,
        fill_color=foreground,
        back_color=background
    )

    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue()


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.markdown("# ⚡ QR STUDIO")

    st.caption("Professional QR Code Generator")

    st.divider()

    page = st.radio(
        "NAVIGATION",
        [
            "🏠 Dashboard",
            "📦 Batch Generator",
            "🕘 QR History",
            "ℹ️ About Project"
        ]
    )

    st.divider()

    st.markdown("### PROJECT STATUS")

    st.success("Generator Ready")

    st.caption("Version 2.0 | Built with Python")


# =====================================================
# DASHBOARD
# =====================================================

if page == "🏠 Dashboard":

    st.title("QR Code Studio Pro")
    st.markdown(
        "Create, customize and download professional QR codes."
    )

    st.write("")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "QR Codes Generated",
            len(st.session_state.history)
        )

    with col2:
        st.metric(
            "QR Formats",
            "7"
        )

    with col3:
        st.metric(
            "Download Formats",
            "PNG + SVG"
        )

    st.divider()

    left, right = st.columns([1.1, 0.9], gap="large")

    with left:

        st.subheader("⚙️ QR Configuration")

        qr_type = st.selectbox(
            "Select QR Code Type",
            [
                "Website URL",
                "Plain Text",
                "Email",
                "Phone Number",
                "SMS",
                "Wi-Fi",
                "vCard"
            ]
        )

        values = {}

        with st.form("qr_form"):

            if qr_type == "Website URL":

                values["url"] = st.text_input(
                    "Website URL",
                    placeholder="https://example.com"
                )

            elif qr_type == "Plain Text":

                values["text"] = st.text_area(
                    "Your Text",
                    placeholder="Enter your message..."
                )

            elif qr_type == "Email":

                values["email"] = st.text_input(
                    "Email Address",
                    placeholder="example@gmail.com"
                )

            elif qr_type == "Phone Number":

                values["phone"] = st.text_input(
                    "Phone Number",
                    placeholder="+91 9876543210"
                )

            elif qr_type == "SMS":

                values["sms_phone"] = st.text_input(
                    "Phone Number"
                )

                values["sms_message"] = st.text_area(
                    "SMS Message"
                )

            elif qr_type == "Wi-Fi":

                values["ssid"] = st.text_input(
                    "Wi-Fi Network Name (SSID)"
                )

                values["wifi_password"] = st.text_input(
                    "Wi-Fi Password",
                    type="password"
                )

                values["security"] = st.selectbox(
                    "Security Type",
                    [
                        "WPA",
                        "WEP",
                        "nopass"
                    ]
                )

            elif qr_type == "vCard":

                values["name"] = st.text_input("Contact Name")
                values["card_phone"] = st.text_input("Contact Phone")
                values["card_email"] = st.text_input("Contact Email")

            st.divider()

            st.markdown("### 🎨 Design Settings")

            foreground = st.color_picker(
                "QR Foreground",
                "#000000"
            )

            background = st.color_picker(
                "QR Background",
                "#FFFFFF"
            )

            size = st.slider(
                "QR Resolution",
                5, 15, 10
            )

            border = st.slider(
                "QR Border",
                2, 8, 4
            )

            submitted = st.form_submit_button(
                "⚡ Generate QR Code",
                use_container_width=True
            )

        st.markdown("### 🖼️ Centre Logo (Optional)")

        logo_file = st.file_uploader(
            "Upload a PNG or JPG logo",
            type=["png", "jpg", "jpeg"],
            help="A small square logo works best."
        )

        if logo_file is not None:
            st.image(logo_file, width=90)

        if submitted:

            try:

                payload = build_payload(qr_type, values)

                if not payload:
                    raise ValueError("Please enter some content.")

                qr_image = make_qr(
                    payload,
                    foreground,
                    background,
                    size,
                    border,
                    logo_file
                )

                png_bytes = image_to_bytes(qr_image)

                st.session_state.current_qr = {
                    "image": png_bytes,
                    "data": payload,
                    "type": qr_type,
                    "foreground": foreground,
                    "background": background,
                    "border": border,
                    "size": size
                }

                st.session_state.history.insert(
                    0,
                    {
                        "type": qr_type,
                        "data": payload,
                        "image": png_bytes
                    }
                )

                st.success("Your QR code has been generated!")

            except Exception as error:
                st.error(str(error))

    with right:

        st.subheader("✨ Live QR Preview")

        current = st.session_state.current_qr

        if current:

            st.image(
                current["image"],
                caption="Your Generated QR Code",
                width=320
            )

            st.success("QR Code Ready")

            st.download_button(
                "⬇️ Download PNG",
                data=current["image"],
                file_name="QR_Studio_Code.png",
                mime="image/png",
                use_container_width=True
            )

            try:

                svg_data = make_svg(
                    current["data"],
                    current["foreground"],
                    current["background"],
                    current["border"]
                )

                st.download_button(
                    "⬇️ Download SVG",
                    data=svg_data,
                    file_name="QR_Studio_Code.svg",
                    mime="image/svg+xml",
                    use_container_width=True
                )

            except Exception:
                st.warning("SVG export is unavailable for this code.")

            with st.expander("QR Code Details"):

                st.write("**Type:**", current["type"])
                st.write("**Resolution:**", current["size"])
                st.write("**Foreground:**", current["foreground"])
                st.write("**Background:**", current["background"])
                st.write("**Border:**", current["border"])

        else:

            st.info("Your QR code preview will appear here.")

            st.markdown("""
            ### Included Features

            - Multiple QR formats
            - Custom colours
            - Centre logo support
            - PNG and SVG export
            - High error correction
            - Downloadable QR codes
            """)


# =====================================================
# BATCH GENERATOR
# =====================================================

elif page == "📦 Batch Generator":

    st.title("📦 Bulk QR Generator")

    st.write(
        "Generate multiple QR codes from a CSV file and download them together."
    )

    st.markdown("""
    Upload a CSV file containing two columns:

    - `name` – File name
    - `data` – Text or URL to encode
    """)

    sample = "name,data\nGoogle,https://google.com\nOpenAI,https://openai.com"

    st.download_button(
        "Download Sample CSV",
        data=sample,
        file_name="sample_qr_data.csv",
        mime="text/csv"
    )

    uploaded_csv = st.file_uploader(
        "Upload your CSV",
        type=["csv"]
    )

    batch_color = st.color_picker(
        "QR Color",
        "#000000",
        key="batch_color"
    )

    batch_bg = st.color_picker(
        "Background Color",
        "#FFFFFF",
        key="batch_bg"
    )

    if uploaded_csv is not None:

        if st.button("Generate All QR Codes", use_container_width=True):

            try:

                text_file = io.StringIO(
                    uploaded_csv.getvalue().decode("utf-8-sig")
                )

                reader = csv.DictReader(text_file)

                if not reader.fieldnames or not {
                    "name", "data"
                }.issubset(set(reader.fieldnames)):

                    raise ValueError(
                        "CSV must contain 'name' and 'data' columns."
                    )

                rows = list(reader)

                if not rows:
                    raise ValueError("CSV contains no records.")

                if len(rows) > 100:
                    raise ValueError("Maximum batch size is 100 QR codes.")

                zip_buffer = io.BytesIO()
                success_count = 0

                with zipfile.ZipFile(
                    zip_buffer,
                    "w",
                    zipfile.ZIP_DEFLATED
                ) as zip_file:

                    for index, row in enumerate(rows, start=1):

                        name = (row.get("name") or "").strip()
                        data = (row.get("data") or "").strip()

                        if not data:
                            continue

                        safe_name = re.sub(
                            r"[^a-zA-Z0-9_-]",
                            "_",
                            name
                        )[:50] or f"QR_{index}"

                        image = make_qr(
                            data,
                            batch_color,
                            batch_bg,
                            10,
                            4
                        )

                        zip_file.writestr(
                            f"{safe_name}.png",
                            image_to_bytes(image)
                        )

                        success_count += 1

                if success_count == 0:
                    raise ValueError("No valid QR records found.")

                st.session_state.batch_zip = zip_buffer.getvalue()
                st.session_state.batch_count = success_count

                st.success(
                    f"{success_count} QR codes generated successfully!"
                )

            except Exception as error:
                st.error(str(error))

    if "batch_zip" in st.session_state:

        st.download_button(
            "⬇️ Download All QR Codes (ZIP)",
            data=st.session_state.batch_zip,
            file_name="QR_Batch_Collection.zip",
            mime="application/zip",
            use_container_width=True
        )


# =====================================================
# HISTORY
# =====================================================

elif page == "🕘 QR History":

    st.title("🕘 Generation History")

    history = st.session_state.history

    if history:

        st.write(
            f"You have generated {len(history)} QR codes in this session."
        )

        for index, item in enumerate(history):

            with st.expander(
                f"{index + 1}. {item['type']} – {item['data'][:45]}"
            ):

                st.image(
                    item["image"],
                    width=200
                )

                st.download_button(
                    "Download Again",
                    data=item["image"],
                    file_name=f"QR_History_{index + 1}.png",
                    mime="image/png",
                    key=f"history_download_{index}"
                )

        if st.button("Clear History"):

            st.session_state.history = []
            st.session_state.current_qr = None
            st.rerun()

    else:

        st.info("No QR codes generated in this session yet.")


# =====================================================
# ABOUT
# =====================================================

elif page == "ℹ️ About Project":

    st.title("ℹ️ About QR Code Studio Pro")

    st.markdown("""
    ### Project Overview

    QR Code Studio Pro is a Python-based QR code generation
    application built with Streamlit.

    It allows users to generate, customize and download QR codes
    for different types of information.

    ### Technology Stack

    - Python
    - Streamlit
    - qrcode
    - Pillow
    - CSV Processing
    - ZIP File Handling

    ### Main Capabilities

    - Custom QR code generation
    - Multiple information formats
    - Logo integration
    - Batch QR generation
    - PNG and SVG downloads    
- Session-based generation history

### Project Purpose

Demonstrates Python programming, file handling, 
image processing, UI development and application 
logic.
""")

st.divider()

st.markdown(
    "**QR Code Studio Pro | Version 2.0**"
)
st.caption("Developed as a beginner-friendly portfolio project.")
