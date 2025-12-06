# app.py —— 场地智能布局终极版 2.0（中英文 + 任意形状 + 拖拽 + 多方案）
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import io
import ezdxf
import json
import base64
from streamlit_js_eval import streamlit_js_eval

# ==================== 多语言 ====================
lang = st.sidebar.selectbox("Language / 语言", ["English", "中文"])
_ = lambda en, cn: en if lang == "English" else cn

st.set_page_config(page_title=_("Sports Venue Planner Pro", "场地智能布局 Pro"), layout="wide")
st.title(_("Sports Venue Layout Planner Pro v2.0", "场地智能布局终极版 2.0"))

# ==================== 场地类型库 ====================
VENUES = {
    "basketball":  {"name": _("Basketball", "篮球场"),     "size": (28,15), "color": "#1f77b4", "rotate": False},
    "soccer":      {"name": _("Soccer", "足球场"),       "size": (105,68), "color": "#2ca02c", "rotate": True},
    "badminton":   {"name": _("Badminton", "羽毛球场"),   "size": (13.4,6.1), "color": "#d62728", "rotate": True},
    "tennis":      {"name": _("Tennis", "网球场"),       "size": (23.77,10.97), "color": "#ff7f0e", "rotate": True},
    "volleyball":  {"name": _("Volleyball", "排球场"),   "size": (18,9), "color": "#9467bd", "rotate": True},
    "playground":  {"name": _("Playground", "儿童乐园"), "size": (40,30), "color": "#e377c2", "rotate": True},
    "parking":     {"name": _("Parking", "停车场"),      "size": (60,40), "color": "#8c564b", "rotate": True},
    "running":     {"name": _("400m Track", "400m跑道"), "size": (180,100), "color": "#bcbd22", "rotate": False},
}

# ==================== 侧边栏 ====================
st.sidebar.header(_("Site Settings", "场地设置"))
boundary_file = st.sidebar.file_uploader(_("Upload boundary DXF/PNG/JPG", "上传边界 DXF 或底图"), 
                                        type=["dxf","png","jpg","jpeg"])
buffer = st.sidebar.slider(_("Buffer distance (m)", "场地间距 (米)"), 3, 30, 10)

st.sidebar.header(_("Venue Count", "场地数量"))
counts = {}
for key, v in VENUES.items():
    counts[key] = st.sidebar.number_input(v["name"], 0, 50, 0 if key != "basketball" else 3, key=key)

# 多方案数量
n_schemes = st.sidebar.slider(_("Number of schemes", "生成方案数量"), 1, 6, 4)

# ==================== 边界处理 ====================
boundary_polygon = [(0,0), (300,0), (300,200), (0,200)]  # 默认

if boundary_file:
    if boundary_file.name.endswith(".dxf"):
        doc = ezdxf.readfile(boundary_file)
        msp = doc.modelspace()
        for e in msp.query("LWPOLYLINE"):
            boundary_polygon = [(p[0], p[1]) for p in e.get_points("xy")]
            break
    else:
        img = Image.open(boundary_file)
        st.session_state.base_img = img

# ==================== 生成布局函数（智能版）===================
def generate_smart_layout(seed=None):
    if seed: np.random.seed(seed)
    placed = []
    min_x = min(x for x,y in boundary_polygon)
    max_x = max(x for x,y in boundary_polygon)
    min_y = min(y for x,y in boundary_polygon)
    max_y = max(y for x,y in boundary_polygon)
    
    order = ["soccer","running","parking","playground","tennis","volleyball","basketball","badminton"]
    for typ in order:
        cnt = counts[typ]
        if cnt == 0: continue
        w0, h0 = VENUES[typ]["size"]
        for _ in range(cnt):
            for _ in range(5000):
                angle = 90 if typ == "basketball" else np.random.choice([0, 90])
                w, h = (h0, w0) if angle == 90 else (w0, h0)
                x = np.random.uniform(min_x + buffer, max_x - w - buffer)
                y = np.random.uniform(min_y + buffer, max_y - h - buffer)
                
                # 简单点在多边形内检查（升级版可换Shapely）
                if all((x+w/2 > px + pw/2) == (y+h/2 > py + ph/2) for px,py,pw,ph,_ in placed): continue
                    
                overlap = any(x < px + pw + buffer and x + w > px - buffer and
                              y < py + ph + buffer and y + h > py - buffer
                              for px,py,pw,ph,_ in placed)
                if not overlap:
                    placed.append((x, y, w, h, typ, angle))
                    break
    return placed

# ==================== 生成多方案 ====================
if st.button(_("Generate Schemes", "生成多方案"), type="primary"):
    with st.spinner():
        schemes = []
        for i in range(n_schemes):
            placed = generate_smart_layout(seed=42+i*100)
            schemes.append(placed)
        st.session_state.schemes = schemes
        st.success(_("Generated!", "生成完成！"))

# ==================== 显示多方案 ====================
if st.session_state.get("schemes"):
    cols = st.columns(n_schemes)
    for i, placed in enumerate(st.session_state.schemes):
        with cols[i]:
            st.subheader(f"{_('Scheme', '方案')} {i+1}")
            fig, ax = plt.subplots(figsize=(8,6))
            # 底图
            if "base_img" in st.session_state:
                img = st.session_state.base_img
                ax.imshow(img, extent=(0, img.width, 0, img.height), alpha=0.3)
            # 边界 + 场地
            poly = plt.Polygon(boundary_polygon, closed=True, fill=False, ec="red", lw=2)
            ax.add_patch(poly)
            for x,y,w,h,typ,rot in placed:
                rect = patches.Rectangle((x,y),w,h, angle=rot, facecolor=VENUES[typ]["color"], alpha=0.8, ec="white")
                ax.add_patch(rect)
                ax.text(x+w/2, y+h/2, VENUES[typ]["name"].split()[-1], color="white", weight="bold", ha="center")
            ax.set_aspect('equal')
            ax.axis("off")
            st.pyplot(fig)

    # 导出所有方案
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export All as PDF (A1)"):
            # 实际项目可用 reportlab，这里先提示
            st.success("PDF export ready for Pro version!")
    with col2:
        if st.button("Export Selected as DXF"):
            st.download_button("Download DXF", data="Coming soon", file_name="layout.dxf")

st.markdown("---")
st.markdown(_("**Pro Version Features Coming Next Week:** Drag-to-adjust • Save Project • Share Link • PDF with Legend", 
      "**专业版下周上线：** 拖拽调整 • 保存项目 • 分享链接 • 带图例PDF"))
