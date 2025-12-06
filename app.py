# app.py —— 终极英制版 4.0 修复版（自动初始化 + 按钮触发生成 + 空列表安全）
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import io
import ezdxf
import tempfile
import os
from ezdxf.enums import TextEntityAlignment

st.set_page_config(page_title="Venue Planner Pro - Imperial v4.0", layout="wide")
st.title("Sports Venue Layout Planner - Imperial Edition v4.0")
st.markdown("**All dimensions in Feet • Full DXF unit control • Custom venues • Basketball N-S**")

# ==================== 单位换算表（内部一律用 Feet） ====================
TO_FEET = {"Feet (ft)": 1.0, "Inch (in)": 1/12, "Meter (m)": 3.28084}
FROM_FEET = {"Feet (ft)": 1.0, "Inch (in)": 12.0, "Meter (m)": 0.3048}

# ==================== 侧边栏设置 ====================
st.sidebar.header("DXF Import Unit")
import_unit = st.sidebar.selectbox("Original DXF unit", ["Feet (ft)", "Inch (in)", "Meter (m)"], index=0)
import_factor = TO_FEET[import_unit]

st.sidebar.header("DXF Export Unit")
export_unit = st.sidebar.selectbox("Export DXF unit", ["Feet (ft)", "Inch (in)", "Meter (m)"], index=0)
export_factor = FROM_FEET[export_unit]

st.sidebar.header("Site Size (Feet)")
col1, col2 = st.sidebar.columns(2)
width_ft  = col1.number_input("East-West width (ft)", value=820.0)   # ≈250m
height_ft = col2.number_input("North-South length (ft)", value=590.0) # ≈180m
buffer_ft = st.sidebar.slider("Buffer between venues (ft)", 10, 100, 30)

uploaded_img = st.sidebar.file_uploader("Upload base map (optional)", type=["png","jpg","jpeg"])
uploaded_dxf = st.sidebar.file_uploader("Upload boundary DXF (optional)", type=["dxf"])

# ==================== DXF边界读取（完美兼容） ====================
boundary_polygon = [(0,0), (width_ft,0), (width_ft,height_ft), (0,height_ft), (0,0)]
actual_width = width_ft
actual_height = height_ft

if uploaded_dxf:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(uploaded_dxf.getvalue())
            tmp_path = tmp.name
        
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()
        points = []
        
        for e in msp.query("LWPOLYLINE"):
            pts = [(p[0]*import_factor, p[1]*import_factor) for p in e.get_points("xy")]
            if len(pts) > 2:
                points = pts
                break
        
        if points:
            boundary_polygon = points + [points[0]]
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            actual_width = max(xs) - min(xs)
            actual_height = max(ys) - min(ys)
            st.success(f"DXF imported! Site size: {actual_width:.1f} × {actual_height:.1f} ft")
        else:
            st.warning("No polygon found, using rectangular site")
    except Exception as e:
        st.error(f"DXF read failed: {e}")
    finally:
        if 'tmp_path' in locals():
            try: os.unlink(tmp_path)
            except: pass

# ==================== 自定义活动空间（全部用 Feet） ====================
if "custom_venues" not in st.session_state:
    st.session_state.custom_venues = [
        {"name": "Basketball Court",  "w": 94,  "h": 50,  "count": 3,  "color": "#1f77b4", "force_ns": True},
        {"name": "Soccer Field",      "w": 345, "h": 223, "count": 0,  "color": "#2ca02c", "force_ns": False},
        {"name": "Tennis Court",      "w": 78,  "h": 36,  "count": 0,  "color": "#ff7f0e", "force_ns": False},
        {"name": "Parking Lot",       "w": 200, "h": 130, "count": 0,  "color": "#8c564b", "force_ns": False},
    ]

def add_venue():
    st.session_state.custom_venues.append({
        "name": "New Space", "w": 100, "h": 80, "count": 1,
        "color": "#"+''.join(np.random.choice(list('0123456789ABCDEF')) for _ in range(6)),
        "force_ns": False
    })

st.sidebar.header("Custom Venues (Feet)")
for i, v in enumerate(st.session_state.custom_venues):
    with st.sidebar.expander(f"{v['name']} ({v['w']}×{v['h']} ft) ×{v['count']}", expanded=True):
        v["name"] = st.text_input("Name", v["name"], key=f"n{i}")
        c1,c2 = st.columns(2)
        v["w"] = c1.number_input("Width (ft)", value=float(v["w"]), key=f"w{i}")
        v["h"] = c2.number_input("Length (ft)", value=float(v["h"]), key=f"h{i}")
        v["count"] = st.number_input("Count", 0, 30, v["count"], key=f"c{i}")
        v["color"] = st.color_picker("Color", v["color"], key=f"col{i}")
        if "basketball" in v["name"].lower():
            v["force_ns"] = True
            st.info("Basketball → Forced North-South")
        else:
            v["force_ns"] = st.checkbox("Force North-South", v["force_ns"], key=f"ns{i}")
        if st.button("Delete", key=f"del{i}"):
            st.session_state.custom_venues.pop(i)
            st.rerun()

if st.sidebar.button("Add New Venue"):
    add_venue()
    st.rerun()

# ==================== 生成布局 ====================
def generate_layout():
    np.random.seed()
    placed = []  # 始终从空列表开始
    for v in st.session_state.custom_venues:
        if v["count"] == 0: continue
        for _ in range(v["count"]):
            for attempt in range(5000):
                x = np.random.uniform(buffer_ft, actual_width - max(v["w"], v["h"]) - buffer_ft)
                y = np.random.uniform(buffer_ft, actual_height - max(v["w"], v["h"]) - buffer_ft)
                w, h = (v["h"], v["w"]) if v["force_ns"] else (v["w"], v["h"])
                # 安全检查：如果 placed 为空，overlap=False
                overlap = False
                if placed:  # 只在非空时检查
                    overlap = any(x < px + pw + buffer_ft and x + w > px - buffer_ft and
                                  y < py + ph + buffer_ft and y + h > py - buffer_ft
                                  for px,py,pw,ph,_ in placed)
                if not overlap:
                    placed.append((x, y, w, h, v["name"], v["color"]))
                    break
            else:
                st.warning(f"Could not place {v['name']} (site too small?)")
    return placed

# ==================== 生成按钮（修复：仅在点击时执行） ====================
if st.button("Generate New Layout", type="primary"):
    with st.spinner("Generating layout in feet..."):
        st.session_state.placed = generate_layout()
    st.success("Layout generated!")

# ==================== 显示结果 ====================
if st.session_state.get("placed"):
    placed = st.session_state.placed
    fig, ax = plt.subplots(figsize=(16,10))
    ax.set_xlim(0, actual_width)
    ax.set_ylim(0, actual_height)
    ax.set_aspect('equal')

    if uploaded_img:
        try:
            img = Image.open(uploaded_img)
            ax.imshow(img, extent=(0, actual_width, 0, actual_height), alpha=0.4, aspect='auto')
        except: pass

    # 边界
    if len(boundary_polygon) > 5:
        poly = plt.Polygon([(p[0], p[1]) for p in boundary_polygon], closed=True, fill=False, ec="red", lw=4)
        ax.add_patch(poly)
    else:
        ax.add_patch(plt.Rectangle((0,0), actual_width, actual_height, fill=False, ec="red", lw=4))

    # 场地
    for x,y,w,h,name,color in placed:
        ax.add_patch(patches.Rectangle((x,y), w, h, fc=color, alpha=0.8, ec="white", lw=2))
        ax.text(x+w/2, y+h/2, f"{name}\n{w:.0f}×{h:.0f} ft", ha='center', va='center',
                color="white", fontsize=10, fontweight="bold")

    ax.set_title(f"Site Layout - {actual_width:.0f} × {actual_height:.0f} ft", fontsize=18)
    ax.set_xlabel("East ←→ West (feet)")
    ax.set_ylabel("South ←→ North (feet)")
    st.pyplot(fig)

    # ==================== 导出 ====================
    c1, c2 = st.columns(2)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    c1.download_button("Download PNG", buf, "layout_feet.png", "image/png")

    # DXF 导出
    doc = ezdxf.new('R2018')
    msp = doc.modelspace()
    scale = export_factor

    if len(boundary_polygon) > 5:
        pts = [(p[0]*scale, p[1]*scale) for p in boundary_polygon]
        msp.add_lwpolyline(pts)
    else:
        msp.add_lwpolyline([(0,0),(actual_width*scale,0),(actual_width*scale,actual_height*scale),(0,actual_height*scale),(0,0)])

    for x,y,w,h,name,_ in placed:
        pts = [(x*scale,y*scale), ((x+w)*scale,y*scale), ((x+w)*scale,(y+h)*scale), (x*scale,(y+h)*scale), (x*scale,y*scale)]
        msp.add_lwpolyline(pts)
        msp.add_text(name, dxfattribs={"height": max(10*scale, 5)}).set_placement(((x+w/2)*scale, (y+h/2)*scale), align=TextEntityAlignment.CENTER)

    dxf_buf = io.BytesIO()
    doc.saveas(dxf_buf)
    dxf_buf.seek(0)
    c2.download_button(f"Export DXF ({export_unit})", dxf_buf, "layout_imperial.dxf", "application/dxf")
else:
    st.info("Configure custom venues in the sidebar → Click 'Generate New Layout' to start")

st.caption("Ultimate Imperial Edition v4.0 (Fixed) • All in Feet • Full DXF Unit Control • Made with Grok")
