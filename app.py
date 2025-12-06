# app.py —— Ultimate Venue Planner v7.0（Architectural Feet 完美支持版 - 修复 KeyError）
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

st.set_page_config(page_title="Venue Planner v7.0 - Imperial", layout="wide")
st.title("Venue Layout Planner – Imperial v7.0")
st.markdown("**All in Feet • Perfect for U.S. Architectural DXF (select Inch!) • Full DXF background**")

# ==================== 单位换算（内部全部用 Feet）===================
TO_FEET   = {"Inch": 1/12, "Feet": 1.0, "Meter": 3.28084}
FROM_FEET = {"Inch": 12.0,  "Feet": 1.0, "Meter": 0.3048}

# ==================== 侧边栏 ====================
st.sidebar.header("DXF Import Unit (VERY IMPORTANT)")
import_unit = st.sidebar.selectbox(
    "Original DXF unit",
    ["Inch ← 99% U.S. Architectural DXF 必选！", "Feet", "Meter"],
    index=0,
    help="美国景观/建筑DXF几乎都是 Architectural Feet（100'-0\" = 1200），必须选 Inch 才能正确显示！"
)
import_factor = TO_FEET[import_unit.split()[0]]

st.sidebar.header("DXF Export Unit")
export_unit = st.sidebar.selectbox("Export DXF unit", ["Feet", "Inch", "Meter"], index=0)
export_factor = FROM_FEET[export_unit.split()[0]]

st.sidebar.header("Site Size (Feet) – only used if no DXF")
col1, col2 = st.sidebar.columns(2)
width_ft  = col1.number_input("E-W width (ft)", value=1000.0)
height_ft = col2.number_input("N-S length (ft)", value=800.0)
buffer_ft = st.sidebar.slider("Buffer between venues (ft)", 10, 150, 40)

uploaded_dxf = st.sidebar.file_uploader("Upload Site DXF (polygon + background)", type=["dxf"])
uploaded_img = st.sidebar.file_uploader("Extra image overlay (optional)", type=["png","jpg","jpeg"])

# ==================== DXF 读取 & 背景提取 ====================
boundary_polygon = [(0,0), (width_ft,0), (width_ft,height_ft), (0,height_ft), (0,0)]
dxf_entities = []
actual_w, actual_h = width_ft, height_ft

if uploaded_dxf:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as f:
            f.write(uploaded_dxf.getvalue())
            tmp_path = f.name
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()

        # 1. 找最外层闭合多边形作为边界
        candidates = []
        for e in msp.query("LWPOLYLINE"):
            if e.closed:
                pts = [(p[0]*import_factor, p[1]*import_factor) for p in e.get_points("xy")]
                if len(pts) > 2:
                    candidates.append(pts)
        if candidates:
            # 选面积最大的
            areas = [abs(sum(pts[i][0]*(pts[(i+1)%len(pts)][1]-pts[i-1][1]) for i in range(len(pts)))) for pts in candidates]
            best = candidates[np.argmax(areas)]
            boundary_polygon = best + [best[0]]
            xs = [p[0] for p in best]
            ys = [p[1] for p in best]
            actual_w = max(xs) - min(xs)
            actual_h = max(ys) - min(ys)
            st.success(f"Boundary loaded: {actual_w:.0f} × {actual_h:.0f} ft")

        # 2. 保存所有实体用于背景绘制
        for e in msp:
            if e.dxftype() in ["LINE","LWPOLYLINE","POLYLINE","CIRCLE","ARC","TEXT","MTEXT","SOLID","HATCH"]:
                dxf_entities.append(e)

        st.info(f"Loaded {len(dxf_entities)} DXF entities as background")
    except Exception as e:
        st.error(f"DXF error: {e}")
    finally:
        if 'tmp_path' in locals():
            try: os.unlink(tmp_path)
            except: pass

# ==================== 自定义场地（Feet）===================
if "custom_venues" not in st.session_state:
    st.session_state.custom_venues = [
        {"name": "Basketball Court", "w": 94,  "h": 50,  "count": 3, "color": "#1f77b4", "force_ns": True},
        {"name": "Soccer Field",     "w": 345, "h": 223, "count": 0, "color": "#2ca02c", "force_ns": False},
        {"name": "Tennis Court",     "w": 78,  "h": 36,  "count": 0, "color": "#ff7f0e", "force_ns": False},
        {"name": "Parking Lot",      "w": 200, "h": 130, "count": 0, "color": "#8c564b", "force_ns": False},
    ]

def add_venue():
    st.session_state.custom_venues.append({
        "name": "New Venue", "w": 120, "h": 80, "count": 1,
        "color": "#"+''.join(np.random.choice("0123456789ABCDEF", 6)),
        "force_ns": False
    })

st.sidebar.header("Custom Venues (Feet)")
for i, v in enumerate(st.session_state.custom_venues):
    with st.sidebar.expander(f"{v['name']} ({v['w']}×{v['h']} ft) ×{v['count']}"):
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
        if st.button("Delete", key=f"d{i}"):
            st.session_state.custom_venues.pop(i)
            st.rerun()

if st.sidebar.button("Add New Venue"):
    add_venue()
    st.rerun()

# ==================== 生成布局 ====================
def generate_layout():
    np.random.seed()
    placed = []
    for v in st.session_state.custom_venues:
        if v["count"] == 0: continue
        for _ in range(v["count"]):
            success = False
            for _ in range(5000):
                x = np.random.uniform(buffer_ft, actual_w - max(v["w"], v["h"]) - buffer_ft)
                y = np.random.uniform(buffer_ft, actual_h - max(v["w"], v["h"]) - buffer_ft)
                w, h = (v["h"], v["w"]) if v["force_ns"] else (v["w"], v["h"])
                overlap = any(
                    x < px + pw + buffer_ft and x + w > px - buffer_ft and
                    y < py + ph + buffer_ft and y + h > py - buffer_ft
                    for px,py,pw,ph,_,_ in placed
                ) if placed else False
                if not overlap:
                    placed.append((x, y, w, h, v["name"], v["color"]))
                    success = True
                    break
            if not success:
                st.toast(f"Could not place one {v['name']}")
    return placed

if st.button("Generate New Layout", type="primary", use_container_width=True):
    with st.spinner("Generating layout..."):
        st.session_state.placed = generate_layout()
    st.success("Layout complete!")

# ==================== 显示结果 ====================
if st.session_state.get("placed"):
    fig, ax = plt.subplots(figsize=(18,11))
    ax.set_xlim(0, actual_w)
    ax.set_ylim(0, actual_h)
    ax.set_aspect('equal')

    # 1. DXF 背景（半透明灰色）
    if dxf_entities:
        for e in dxf_entities:
            try:
                if e.dxftype() == "LINE":
                    x1,y1 = e.dxf.start[0]*import_factor, e.dxf.start[1]*import_factor
                    x2,y2 = e.dxf.end[0]*import_factor,   e.dxf.end[1]*import_factor
                    ax.plot([x1,x2],[y1,y2], color="#555555", alpha=0.6, lw=0.8)
                elif e.dxftype() == "LWPOLYLINE":
                    pts = [(p[0]*import_factor, p[1]*import_factor) for p in e.get_points("xy")]
                    x,y = zip(*pts)
                    if e.closed:
                        ax.fill(x, y, color="lightgray", alpha=0.25)
                    ax.plot(x, y, color="#555555", alpha=0.6, lw=0.8)
                elif e.dxftype() == "TEXT":
                    x,y = e.dxf.insert[0]*import_factor, e.dxf.insert[1]*import_factor
                    ax.text(x, y, e.dxf.text, fontsize=5, color="#333333", alpha=0.7)
            except: pass

    # 2. 边界高亮
    if boundary_polygon:
        ax.add_patch(plt.Polygon(boundary_polygon, closed=True, fill=False, ec="red", lw=5, alpha=0.9))

    # 3. 新场地
    for x,y,w,h,name,color in st.session_state.placed:
        ax.add_patch(patches.Rectangle((x,y), w, h, fc=color, alpha=0.85, ec="white", lw=3))
        ax.text(x+w/2, y+h/2, f"{name}\n{w:.0f}×{h:.0f} ft",
                ha='center', va='center', color="white", fontsize=11, fontweight="bold")

    # 4. 额外图片叠加
    if uploaded_img:
        try:
            img = Image.open(uploaded_img)
            ax.imshow(img, extent=(0,actual_w,0,actual_h), alpha=0.3, aspect='auto')
        except: pass

    ax.set_title(f"Final Layout – {actual_w:.0f} × {actual_h:.0f} ft", fontsize=20)
    ax.set_xlabel("East ←→ West (feet)"); ax.set_ylabel("South ←→ North (feet)")
    st.pyplot(fig)

    # ==================== 导出 ====================
    c1, c2 = st.columns(2)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=300, bbox_inches='tight'); buf.seek(0)
    c1.download_button("Download PNG", buf, "layout.png", "image/png")

    doc = ezdxf.new('R2018')
    msp = doc.modelspace()
    scale = export_factor
    pts = boundary_polygon if len(boundary_polygon)>5 else [(0,0),(actual_w,0),(actual_w,actual_h),(0,actual_h),(0,0)]
    msp.add_lwpolyline([(p[0]*scale, p[1]*scale) for p in pts])
    for x,y,w,h,name,_ in st.session_state.placed:
        rect = [(x*scale,y*scale), ((x+w)*scale,y*scale), ((x+w)*scale,(y+h)*scale), (x*scale,(y+h)*scale), (x*scale,y*scale)]
        msp.add_lwpolyline(rect)
        msp.add_text(name, dxfattribs={"height": max(15*scale,5)}).set_placement(((x+w/2)*scale, (y+h/2)*scale), align=TextEntityAlignment.CENTER)
    dxf_buf = io.BytesIO(); doc.saveas(dxf_buf); dxf_buf.seek(0)
    c2.download_button(f"Export DXF ({export_unit.split()[0]})", dxf_buf, "final_layout.dxf", "application/dxf")
else:
    st.info("Upload your DXF → Click **Generate New Layout** → Done!")

st.caption("Ultimate v7.0 • Perfect for U.S. Architectural DXF (select Inch!) • Made with Grok")
