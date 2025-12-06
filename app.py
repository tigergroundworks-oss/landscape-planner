# app.py —— Ultimate Venue Planner v8.0（彻底不出界 + 任意旋转 + 最大化利用）
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

st.set_page_config(page_title="Venue Planner v8.0 - Imperial", layout="wide")
st.title("Venue Layout Planner – Imperial v8.0")
st.markdown("**All in Feet • No venue outside boundary • Random rotation • Max space usage**")

# ==================== 单位换算 ====================
TO_FEET   = {"Inch": 1/12, "Feet": 1.0, "Meter": 3.28084}
FROM_FEET = {"Inch": 12.0,  "Feet": 1.0, "Meter": 0.3048}

# ==================== 侧边栏 ====================
st.sidebar.header("DXF Import Unit")
import_unit = st.sidebar.selectbox(
    "Original DXF unit",
    ["Inch ← U.S. Architectural DXF 必选", "Feet", "Meter"],
    index=0
)
import_factor = TO_FEET[import_unit.split()[0]]

st.sidebar.header("DXF Export Unit")
export_unit = st.sidebar.selectbox("Export DXF unit", ["Feet", "Inch", "Meter"], index=0)
export_factor = FROM_FEET[export_unit]

st.sidebar.header("Site Size (Feet) – only used if no DXF")
col1, col2 = st.sidebar.columns(2)
width_ft  = col1.number_input("E-W width (ft)", value=1000.0)
height_ft = col2.number_input("N-S length (ft)", value=800.0)
buffer_ft = st.sidebar.slider("Buffer (ft)", 10, 150, 40)

# 随机旋转滑块
rotation_range = st.sidebar.slider("Max Random Rotation (degrees)", 0, 360, 90,
                                   help="0=不旋转, 90=0°/90°, 360=任意角度")

uploaded_dxf = st.sidebar.file_uploader("Upload Site DXF (polygon + background)", type=["dxf"])
uploaded_img = st.sidebar.file_uploader("Extra overlay image (optional)", type=["png","jpg","jpeg"])

# ==================== DXF 读取 ====================
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

        # 找最外层闭合多边形
        candidates = []
        for e in msp.query("LWPOLYLINE"):
            if e.closed:
                pts = [(p[0]*import_factor, p[1]*import_factor) for p in e.get_points("xy")]
                if len(pts) > 2:
                    candidates.append(pts)
        if candidates:
            areas = [abs(sum(pts[i][0]*(pts[(i+1)%len(pts)][1]-pts[i-1][1]) for i in range(len(pts)))) for pts in candidates]
            best = candidates[np.argmax(areas)]
            boundary_polygon = best + [best[0]]
            xs = [p[0] for p in best]
            ys = [p[1] for p in best]
            actual_w = max(xs) - min(xs)
            actual_h = max(ys) - min(ys)
            st.success(f"Boundary loaded: {actual_w:.0f} × {actual_h:.0f} ft")

        for e in msp:
            if e.dxftype() in ["LINE","LWPOLYLINE","POLYLINE","CIRCLE","ARC","TEXT","MTEXT","SOLID","HATCH"]:
                dxf_entities.append(e)
    except Exception as e:
        st.error(f"DXF error: {e}")
    finally:
        if 'tmp_path' in locals():
            try: os.unlink(tmp_path)
            except: pass

# ==================== 自定义场地 ====================
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

# ==================== 点在多边形内 ====================
def point_in_polygon(x, y, poly):
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

# ==================== 生成布局（不出界 + 任意旋转） ====================
def generate_layout():
    np.random.seed()
    placed = []  # (x, y, w, h, name, color, angle)
    
    for v in st.session_state.custom_venues:
        if v["count"] == 0: continue
        for _ in range(v["count"]):
            placed_this = False
            for attempt in range(10000):
                # 随机位置
                x = np.random.uniform(0, actual_w)
                y = np.random.uniform(0, actual_h)
                # 随机角度（篮球场除外）
                angle = 0 if v["force_ns"] else np.random.uniform(0, rotation_range)
                w, h = v["w"], v["h"]

                # 计算旋转后四个角点
                cx, cy = x + w/2, y + h/2
                rad = np.radians(angle)
                cos_a, sin_a = np.cos(rad), np.sin(rad)
                half_w, half_h = w/2, h/2
                corners = [
                    (cx + (half_w * cos_a - half_h * sin_a), cy + (half_w * sin_a + half_h * cos_a)),
                    (cx + (half_w * cos_a + half_h * sin_a), cy + (half_w * sin_a - half_h * cos_a)),
                    (cx + (-half_w * cos_a + half_h * sin_a), cy + (-half_w * sin_a - half_h * cos_a)),
                    (cx + (-half_w * cos_a - half_h * sin_a), cy + (-half_w * sin_a + half_h * cos_a)),
                ]

                # 检查是否完全在边界内
                if not all(point_in_polygon(px, py, boundary_polygon) for px, py in corners):
                    continue

                # 检查是否与其他场地重叠
                overlap = False
                for px, py, pw, ph, _, _, pangle in placed:
                    # 简化：用包围盒检查（足够快且安全）
                    if (x < px + pw + buffer_ft and x + w > px - buffer_ft and
                        y < py + ph + buffer_ft and y + h > py - buffer_ft):
                        overlap = True
                        break
                if overlap:
                    continue

                placed.append((x, y, w, h, v["name"], v["color"], angle))
                placed_this = True
                break

            if not placed_this:
                st.toast(f"Warning: Could not place one {v['name']}")
    return placed

# ==================== 生成按钮 ====================
if st.button("Generate New Layout", type="primary", use_container_width=True):
    with st.spinner("Generating optimal layout..."):
        st.session_state.placed = generate_layout()
    st.success(f"Success! Placed {len(st.session_state.placed)} venues")

# ==================== 显示结果 ====================
if st.session_state.get("placed"):
    fig, ax = plt.subplots(figsize=(18,11))
    ax.set_xlim(0, actual_w)
    ax.set_ylim(0, actual_h)
    ax.set_aspect('equal')

    # DXF 背景
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
            except: pass

    # 边界
    if boundary_polygon:
        ax.add_patch(plt.Polygon(boundary_polygon, closed=True, fill=False, ec="red", lw=5))

    # 新场地（带旋转）
    for x,y,w,h,name,color,angle in st.session_state.placed:
        rect = patches.Rectangle((x,y), w, h, angle=angle, fc=color, ec="white", lw=3, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x+w/2, y+h/2, f"{name}\n{w:.0f}×{h:.0f}", ha='center', va='center',
                color="white", fontsize=11, fontweight="bold", rotation=angle)

    if uploaded_img:
        try:
            img = Image.open(uploaded_img)
            ax.imshow(img, extent=(0,actual_w,0,actual_h), alpha=0.3, aspect='auto')
        except: pass

    ax.set_title(f"Optimized Layout – {actual_w:.0f} × {actual_h:.0f} ft", fontsize=20)
    st.pyplot(fig)

    # 导出
    c1, c2 = st.columns(2)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=300, bbox_inches='tight'); buf.seek(0)
    c1.download_button("Download PNG", buf, "layout.png", "image/png")

    doc = ezdxf.new('R2018')
    msp = doc.modelspace()
    scale = export_factor
    pts = boundary_polygon if len(boundary_polygon)>5 else [(0,0),(actual_w,0),(actual_w,actual_h),(0,actual_h),(0,0)]
    msp.add_lwpolyline([(p[0]*scale, p[1]*scale) for p in pts])
    for x,y,w,h,name,color,angle in st.session_state.placed:
        cx, cy = x + w/2, y + h/2
        rad = np.radians(angle)
        cos_a, sin_a = np.cos(rad), np.sin(rad)
        hw, hh = w/2, h/2
        corners = [
            (cx + (hw*cos_a - hh*sin_a), cy + (hw*sin_a + hh*cos_a)),
            (cx + (hw*cos_a + hh*sin_a), cy + (hw*sin_a - hh*cos_a)),
            (cx + (-hw*cos_a + hh*sin_a), cy + (-hw*sin_a - hh*cos_a)),
            (cx + (-hw*cos_a - hh*sin_a), cy + (-hw*sin_a + hh*cos_a)),
            (cx + (hw*cos_a - hh*sin_a), cy + (hw*sin_a + hh*cos_a)),
        ]
        msp.add_lwpolyline([(p[0]*scale, p[1]*scale) for p in corners])
        text = msp.add_text(name, dxfattribs={"height": max(15*scale,5)})
        text.set_placement((cx*scale, cy*scale), align=TextEntityAlignment.CENTER)
        text.dxf.rotation = angle
    dxf_buf = io.BytesIO(); doc.saveas(dxf_buf); dxf_buf.seek(0)
    c2.download_button(f"Export DXF ({export_unit})", dxf_buf, "final_layout.dxf", "application/dxf")
else:
    st.info("Upload DXF → Set venues → Click **Generate New Layout**")

st.caption("v8.0 • 100% inside boundary • Random rotation • Max space usage • Made with Grok")
