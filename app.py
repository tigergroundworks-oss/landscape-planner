# app.py —— 终极版 3.5（DXF导入+导出 全部支持 Feet/Inch/Meter）
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import io
import ezdxf
from ezdxf.enums import TextEntityAlignment

st.set_page_config(page_title="Ultimate Venue Planner 3.5", layout="wide")
st.title("Ultimate Venue Layout Planner v3.5")
st.markdown("**DXF 导入支持 Feet/Inch/Meter • 导出也支持三种单位 • 完全自定义场地**")

# ==================== 侧边栏：DXF 导入单位 ====================
st.sidebar.header("DXF Import Unit (when uploading boundary)")
import_unit = st.sidebar.selectbox(
    "DXF 原始单位 / Original DXF Unit",
    options=["Meter (m)", "Feet (ft)", "Inch (in)"],
    index=0,
    help="选择你上传的DXF文件使用的单位，程序会自动转换为米"
)

# 导入单位 → 米的换算系数
import_factor = {
    "Meter (m)": 1.0,
    "Feet (ft)": 0.3048,      # 1 ft = 0.3048 m
    "Inch (in)": 0.0254       # 1 in = 0.0254 m
}[import_unit]

# ==================== 侧边栏：DXF 导出单位 ====================
st.sidebar.header("DXF Export Unit")
export_unit = st.sidebar.selectbox(
    "导出DXF单位 / Export Unit",
    options=["Meter (m)", "Feet (ft)", "Inch (in)"],
    index=0
)
export_factor = {
    "Meter (m)": 1.0,
    "Feet (ft)": 3.28084,
    "Inch (in)": 39.3701
}[export_unit]

# ==================== 场地尺寸 & 底图 ====================
default_w, default_h = 300.0, 200.0
width  = st.sidebar.number_input("场地宽度 E-W (m)", value=default_w)
height = st.sidebar.number_input("场地长度 N-S (m)", value=default_h)
buffer = st.sidebar.slider("场地间距 Buffer (m)", 3, 50, 10)

uploaded_img = st.sidebar.file_uploader("上传底图 Base Map", type=["png","jpg","jpeg"])
uploaded_dxf = st.sidebar.file_uploader("上传边界DXF (可选) / Upload Boundary DXF", type=["dxf"])

# ==================== 读取DXF边界（支持单位换算） ====================
boundary_polygon = [(0,0), (width,0), (width,height), (0,height), (0,0)]

if uploaded_dxf:
    try:
        doc = ezdxf.readfile(uploaded_dxf)
        msp = doc.modelspace()
        points = []
        for e in msp.query("LWPOLYLINE CIRCLE ARC LINE"):
            if e.dxftype() == "LWPOLYLINE":
                pts = e.get_points("xy")
                points = [(p[0]*import_factor, p[1]*import_factor) for p in pts]
                break
        if points:
            boundary_polygon = points + [points[0]]
            # 自动更新场地尺寸为DXF实际范围
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)
            st.success(f"DXF导入成功！场地尺寸自动设为 {width:.1f}×{height:.1f} m")
        else:
            st.warning("未识别到有效边界，使用矩形场地")
    except Exception as e:
        st.error(f"DXF读取失败: {e}")

# ==================== 自定义场地管理（同上一版） ====================
if 'custom_venues' not in st.session_state:
    st.session_state.custom_venues = [
        {"name": "Basketball Court", "w": 28, "h": 15, "count": 3, "color": "#1f77b4", "force_ns": True},
        {"name": "Soccer Field",     "w": 105,"h": 68, "count": 0, "color": "#2ca02c", "force_ns": False},
        {"name": "Badminton",        "w": 13.4,"h": 6.1,"count": 12,"color": "#d62728", "force_ns": False},
    ]

def add_venue(): 
    st.session_state.custom_venues.append({"name":"New Space","w":30,"h":20,"count":1,"color":"#ff7f0e","force_ns":False})
def delete_venue(i): 
    st.session_state.custom_venues.pop(i)

st.sidebar.header("Custom Venues")
for i, v in enumerate(st.session_state.custom_venues):
    with st.sidebar.expander(f"{v['name']} ({v['w']}×{v['h']}m) ×{v['count']}", expanded=True):
        v["name"] = st.text_input("Name", v["name"], key=f"n{i}")
        c1,c2 = st.columns(2)
        v["w"] = c1.number_input("Width(m)", value=float(v["w"]), key=f"w{i}")
        v["h"] = c2.number_input("Height(m)", value=float(v["h"]), key=f"h{i}")
        v["count"] = st.number_input("Count", 0, 50, v["count"], key=f"c{i}")
        v["color"] = st.color_picker("Color", v["color"], key=f"col{i}")
        if "basketball" in v["name"].lower():
            v["force_ns"] = True
            st.info("Basketball detected → Forced N-S")
        else:
            v["force_ns"] = st.checkbox("Force North-South", v["force_ns"], key=f"ns{i}")
        if st.button("Delete", key=f"d{i}"):
            delete_venue(i); st.rerun()

if st.sidebar.button("Add New Venue"):
    add_venue(); st.rerun()

# ==================== 生成布局 ====================
def generate_layout():
    np.random.seed()
    placed = []
    for v in st.session_state.custom_venues:
        if v["count"] == 0: continue
        for _ in range(v["count"]):
            for _ in range(5000):
                x = np.random.uniform(buffer, width - max(v["w"], v["h"]) - buffer)
                y = np.random.uniform(buffer, height - max(v["w"], v["h"]) - buffer)
                w, h = (v["h"], v["w"]) if v["force_ns"] else (v["w"], v["h"])
                if any(x < px + pw + buffer and x + w > px - buffer and
                       y < py + ph + buffer and y + h > py - buffer
                       for px,py,pw,ph,_ in placed):
                    continue
                placed.append((x, y, w, h, v["name"], v["color"]))
                break
    return placed

if st.button("Generate Layout", type="primary"):
    with st.spinner("Generating..."):
        st.session_state.placed = generate_layout()
    st.success("Done!")

# ==================== 显示 + 导出 ====================
if st.session_state.get("placed"):
    fig, ax = plt.subplots(figsize=(16,10))
    ax.set_xlim(0, width); ax.set_ylim(0, height); ax.set_aspect('equal')
    
    if uploaded_img:
        img = Image.open(uploaded_img)
        ax.imshow(img, extent=(0,width,0,height), alpha=0.35)
    
    # 绘制边界
    if len(boundary_polygon) > 5:
        poly = plt.Polygon([(p[0], p[1]) for p in boundary_polygon], closed=True, fill=False, ec="red", lw=4)
        ax.add_patch(poly)
    else:
        ax.add_patch(plt.Rectangle((0,0), width, height, fill=False, ec="red", lw=4))
    
    for x,y,w,h,name,color in st.session_state.placed:
        ax.add_patch(patches.Rectangle((x,y), w, h, fc=color, alpha=0.8, ec="white", lw=2))
        ax.text(x+w/2, y+h/2, f"{name}\n{w:.0f}×{h:.0f}", ha='center', va='center', color="white", fontsize=9, fontweight="bold")
    
    st.pyplot(fig)
    
    c1, c2 = st.columns(2)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=300, bbox_inches='tight'); buf.seek(0)
    c1.download_button("Download PNG", buf, "layout.png", "image/png")
    
    # DXF 导出（使用导出单位）
    doc = ezdxf.new('R2018')
    msp = doc.modelspace()
    scale = export_factor
    
    # 边界
    if len(boundary_polygon) > 5:
        pts = [(p[0]*scale, p[1]*scale) for p in boundary_polygon]
        msp.add_lwpolyline(pts)
    else:
        msp.add_lwpolyline([(0,0),(width*scale,0),(width*scale,height*scale),(0,height*scale),(0,0)])
    
    # 场地
    for x,y,w,h,name,_ in st.session_state.placed:
        pts = [(x*scale,y*scale), ((x+w)*scale,y*scale), ((x+w)*scale,(y+h)*scale), (x*scale,(y+h)*scale), (x*scale,y*scale)]
        msp.add_lwpolyline(pts)
        msp.add_text(name, dxfattribs={"height": max(3*scale, 1)}).set_placement(((x+w/2)*scale, (y+h/2)*scale), align=TextEntityAlignment.CENTER)
    
    dxf_buf = io.BytesIO(); doc.saveas(dxf_buf); dxf_buf.seek(0)
    c2.download_button(f"Export DXF ({export_unit.split()[0]})", dxf_buf, "layout_final.dxf", "application/dxf")
else:
    st.info("请上传DXF或设置场地 → 点击 Generate Layout 开始")

st.caption("Ultimate Version 3.5 • DXF Import & Export support Meter/Feet/Inch • Fully Customizable")
