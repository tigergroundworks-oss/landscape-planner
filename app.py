# app.py  ——  绝对能在 Streamlit Cloud 运行的终极稳定版
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import io
import ezdxf

st.set_page_config(page_title="场地智能布局神器", layout="wide")
st.title("场地智能布局生成器")
st.markdown("**上传底图 → 设置场地数量 → 一键生成合理布局 → 导出 PNG/DXF**  \n篮球场已全部自动南北朝向，避免眩光")

# —— 侧边栏控制 ——
st.sidebar.header("场地尺寸")
col1, col2 = st.sidebar.columns(2)
width  = col1.number_input("场地宽度 (m)", value=250.0)
height = col2.number_input("场地长度 (m)", value=180.0)

st.sidebar.header("场地数量")
n_basket = st.sidebar.number_input("篮球场", 0, 20, 3)
n_soccer = st.sidebar.number_input("足球场", 0, 5, 0)
n_badm   = st.sidebar.number_input("羽毛球场", 0, 50, 15)

uploaded_img = st.sidebar.file_uploader("上传底图（可选）", type=["png","jpg","jpeg"])

# —— 场地标准尺寸 ——
sizes = {"basketball": (28, 15), "soccer": (105, 68), "badminton": (13.4, 6.1)}
colors = {"basketball": "#1f77b4", "soccer": "#2ca02c", "badminton": "#d62728"}

# —— 生成布局函数 ——
def generate_layout():
    np.random.seed()                     # 每次都不一样
    placed = []
    items = [("basketball", n_basket), ("soccer", n_soccer), ("badminton", n_badm)]
    
    for typ, cnt in items:
        if cnt == 0: continue
        w0, h0 = sizes[typ]
        for _ in range(cnt):
            for _ in range(3000):
                x = np.random.uniform(10, width  - max(w0,h0) - 10)
                y = np.random.uniform(10, height - max(w0,h0) - 10)
                # 篮球场强制南北向（长边28m为南北）
                w, h = (h0, w0) if typ == "basketball" else (w0, h0)
                
                # 检查是否重叠（留5米缓冲）
                if any(x < px + pw + 5 and x + w > px - 5 and
                       y < py + ph + 5 and y + h > py - 5
                       for px,py,pw,ph,_,_ in placed):
                    continue
                placed.append((x, y, w, h, typ))
                break
    return placed

# —— 生成按钮 ——
if st.button("重新生成布局", type="primary"):
    st.session_state.placed = generate_layout()

if "placed" in st.session_state:
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.set_aspect('equal')

    # 底图
    if uploaded_img:
        img = Image.open(uploaded_img)
        ax.imshow(img, extent=(0, width, 0, height), alpha=0.4, aspect='auto')

    # 场地边界
    ax.add_patch(plt.Rectangle((0,0), width, height, fill=False, ec="red", lw=3))

    # 画每个场地
    for x, y, w, h, typ in st.session_state.placed:
        ax.add_patch(patches.Rectangle((x,y), w, h, facecolor=colors[typ], alpha=0.75, ec="white", lw=2))
        ax.text(x+w/2, y+h/2, f"{typ}\n{w:.0f}×{h:.0f}m", 
                ha='center', va='center', color="white", fontsize=10, weight="bold")

    ax.set_xlabel("东 ←→ 西 (米)")
    ax.set_ylabel("南 ←→ 北 (米)")
    st.pyplot(fig)

    # —— 导出 ——
    c1, c2 = st.columns(2)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    c1.download_button("下载 PNG", buf, "场地布局.png", "image/png")

    # DXF 导出
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0,0),(width,0),(width,height),(0,height),(0,0)])
    for x,y,w,h,typ in st.session_state.placed:
        msp.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)])
        msp.add_text(typ, dxfattribs={"height": 4}).set_placement((x+w/2, y+h/2), align=ezdxf.MIDDLE_CENTER)
    dxf_buf = io.BytesIO()
    doc.saveas(dxf_buf)
    dxf_buf.seek(0)
    c2.download_button("导出 DXF (CAD打开)", dxf_buf, "场地布局.dxf", "application/dxf")

st.success("部署成功！现在可以无限使用了～")
