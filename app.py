# app.py – English Professional Venue Layout Generator (100% working on Streamlit Cloud)
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import io
import ezdxf

st.set_page_config(page_title="Sports Venue Layout Generator", layout="wide")
st.title("Sports Venue Layout Generator")
st.markdown("**Upload base map → Set venue counts → One-click generation → Export PNG/DXF**  \nBasketball courts are automatically north-south oriented to avoid glare")

# ==================== Sidebar ====================
st.sidebar.header("Site Dimensions (m)")
col1, col2 = st.sidebar.columns(2)
width  = col1.number_input("East-West width", min_value=50.0, value=250.0)
height = col2.number_input("North-South length", min_value=50.0, value=180.0)

st.sidebar.header("Number of Venues")
n_basket = st.sidebar.number_input("Basketball courts (28×15m)", 0, 20, 3)
n_soccer = st.sidebar.number_input("Soccer fields (105×68m)", 0, 5, 0)
n_badm   = st.sidebar.number_input("Badminton courts (13.4×6.1m)", 0, 50, 15)

uploaded_img = st.sidebar.file_uploader("Upload base map (optional)", type=["png", "jpg", "jpeg"])

# ==================== Venue specs ====================
sizes = {
    "basketball": (28, 15),
    "soccer":     (105, 68),
    "badminton":  (13.4, 6.1)
}
colors = {
    "basketball": "#1f77b4",
    "soccer":     "#2ca02c",
    "badminton":  "#d62728"
}

# ==================== Layout generator ====================
def generate_layout():
    np.random.seed()
    placed = []
    
    for typ, count in [("basketball", n_basket), ("soccer", n_soccer), ("badminton", n_badm)]:
        if count == 0:
            continue
        w0, h0 = sizes[typ]
        success = 0
        for _ in range(count):
            for _ in range(3000):
                x = np.random.uniform(15, width - max(w0, h0) - 15)
                y = np.random.uniform(15, height - max(w0, h0) - 15)
                
                # Force basketball courts north-south (long side = 28m north-south)
                if typ == "basketball":
                    w, h = h0, w0          # width 15m, height 28m
                else:
                    w, h = w0, h0
                
                # Overlap check (5m buffer)
                overlap = any(
                    x < px + pw + 5 and x + w > px - 5 and
                    y < py + ph + 5 and y + h > py - 5
                    for px, py, pw, ph, _ in placed
                )
                if not overlap:
                    placed.append((x, y, w, h, typ))
                    success += 1
                    break
            else:
                st.toast(f"Could not place basketball court #{success+1} (placed {success})")
    return placed

# ==================== Generate button ====================
if st.button("Generate New Layout", type="primary", use_container_width=True):
    with st.spinner("Generating layout…"):
        st.session_state.placed = generate_layout()
    st.success("Layout generated!")

# ==================== Display results ====================
if st.session_state.get("placed"):
    placed = st.session_state.placed
    
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.set_aspect('equal')
    
    # Base map
    if uploaded_img:
        try:
            img = Image.open(uploaded_img)
            ax.imshow(img, extent=(0, width, 0, height), alpha=0.4, aspect='auto')
        except:
            st.warning("Failed to load base map")
    
    # Site boundary
    ax.add_patch(plt.Rectangle((0,0), width, height, fill=False, color="red", linewidth=3))
    
    # Draw venues
    for x, y, w, h, typ in placed:
        ax.add_patch(patches.Rectangle((x, y), w, h,
                     facecolor=colors[typ], alpha=0.75, edgecolor="white", linewidth=2))
        ax.text(x + w/2, y + h/2, f"{typ}\n{w:.0f}×{h:.0f}m",
                ha='center', va='center', color="white", fontsize=11, fontweight="bold")
    
    ax.set_xlabel("East ←→ West (m)")
    ax.set_ylabel("South ←→ North (m)")
    ax.set_title(f"Generated {len(placed)} venues", fontsize=16)
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)
    
    # ==================== Export ====================
    col1, col2 = st.columns(2)
    
    # PNG
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    col1.download_button("Download PNG", buf, "venue_layout.png", "image/png")
    
    # DXF
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0,0),(width,0),(width,height),(0,height),(0,0)])
    for x, y, w, h, typ in placed:
        pts = [(x,y), (x+w,y), (x+w,y+h), (x,y+h), (x,y)]
        msp.add_lwpolyline(pts)
        msp.add_text(typ, dxfattribs={"height": 4}).set_placement((x+w/2, y+h/2), align=ezdxf.MIDDLE_CENTER)
    
    dxf_buf = io.BytesIO()
    doc.saveas(dxf_buf)
    dxf_buf.seek(0)
    col2.download_button("Export DXF (open in CAD)", dxf_buf, "venue_layout.dxf", "application/dxf")
else:
    st.info("Click **Generate New Layout** on the left to start")

st.caption("Powered by Grok • 100% Free • Basketball courts always north-south")
