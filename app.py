# 文件名：app.py   （完整专业版，修复版）
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import io
import base64
import ezdxf
from ezdxf import units

# ==================== 页面设置 ====================
st.set_page_config(page_title="场地智能布局神器", layout="wide")
st.title("🏟️ 场地智能布局生成器 Pro")
st.markdown("**上传底图 → 设置边界 → 调节数量 → 一键生成 → 导出 DXF/PNG**  | 篮球场自动南北朝向，避免眩光")

# ==================== 侧边栏 ====================
st.sidebar.header("1. 场地边界")
boundary_mode = st.sidebar.radio("边界方式", ["手动矩形", "上传DXF提取"])

st.sidebar.header("2. 底图上传（可选）")
uploaded_image = st.sidebar.file_uploader("上传PNG/JPG底图", type=["png", "jpg", "jpeg"])

st.sidebar.header("3. 场地数量")
n_basket = st.sidebar.number_input("篮球场 (28×15m)", min_value=0, max_value=20, value=2)
n_soccer = st.sidebar.number_input("足球场 (105×68m)", min_value=0, max_value=5, value=0)
n_badm = st.sidebar.number_input("羽毛球场 (13.4×6.1m)", min_value=0, max_value=50, value=8)
st.sidebar.caption("💡 篮球场强制南北向布置")

# ==================== 尺寸 & 颜色 ====================
item_sizes = {
    'basketball': (28, 15),
    'soccer': (105, 68),
    'badminton': (13.4, 6.1)
}
colors = {'basketball': '#1f77b4', 'soccer': '#2ca02c', 'badminton': '#d62728'}

# ==================== 边界处理 ====================
boundary_polygon = [(0,0), (200,0), (200,150), (0,150)]
if boundary_mode == "手动矩形":
    col1, col2 = st.columns(2)
    x_max = col1.number_input("东西宽度 (m)", value=200.0)
    y_max = col2.number_input("南北长度 (m)", value=150.0)
    boundary_polygon = [(0,0), (x_max,0), (x_max,y_max), (0,y_max)]
elif boundary_mode == "上传DXF提取":
    uploaded_dxf = st.sidebar.file_uploader("上传DXF文件", type=["dxf"])
    if uploaded_dxf:
        try:
            doc = ezdxf.readfile(uploaded_dxf)
            msp = doc.modelspace()
            points = []
            for entity in msp:
                if entity.dxftype() == 'LWPOLYLINE':
                    points = [(p[0], p[1]) for p in entity.get_points('xy')]
                    break
            if points:
                boundary_polygon = points + [points[0]]
                st.sidebar.success("DXF边界加载成功！")
            else:
                st.sidebar.warning("未找到轮廓，使用默认边界")
        except Exception as e:
            st.sidebar.error(f"DXF加载失败: {e}")

# ==================== 点在多边形内算法 ====================
def point_in_polygon(x, y, poly):
    n = len(poly) - 1  # 闭合多边形
    inside = False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def rect_fully_inside(x, y, w, h, poly):
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return all(point_in_polygon(cx, cy, poly) for cx, cy in corners)

# ==================== 生成布局 ====================
@st.cache_data
def generate_layout(_n_basket, _n_soccer, _n_badm, _boundary):
    np.random.seed(42)  # 固定种子，便于调试
    placed = []
    items = [
        ('basketball', _n_basket),
        ('soccer', _n_soccer),
        ('badminton', _n_badm)
    ]
    min_x = min(p[0] for p in _boundary)
    min_y = min(p[1] for p in _boundary)
    max_x = max(p[0] for p in _boundary)
    max_y = max(p[1] for p in _boundary)

    for typ, count in items:
        if count == 0:
            continue
        orig_w, orig_h = item_sizes[typ]
        for _ in range(count):
            attempts = 0
            while attempts < 1000:
                x = np.random.uniform(min_x + 5, max_x - max(orig_w, orig_h) - 5)
                y = np.random.uniform(min_y + 5, max_y - max(orig_w, orig_h) - 5)
                
                # 篮球场旋转南北向
                if typ == 'basketball':
                    w, h = orig_h, orig_w  # 宽15，高28
                else:
                    w, h = orig_w, orig_h
                
                if rect_fully_inside(x, y, w, h, _boundary):
                    overlap = False
                    for px, py, pw, ph, _, _ in placed:
                        if not (x + w + 5 < px or x > px + pw + 5 or y + h + 5 < py or y > py + ph + 5):
                            overlap = True
                            break
                    if not overlap:
                        placed.append((x, y, w, h, typ, 90 if typ == 'basketball' else 0))
                        break
                attempts += 1
            if attempts == 1000:
                st.warning(f"无法放置所有 {typ}，已放置 {len([p for p in placed if p[4] == typ])} 个")
    return placed

# ==================== 生成按钮 ====================
if st.button("🎲 生成布局", type="primary"):
    placed = generate_layout(n_basket, n_soccer, n_badm, boundary_polygon)
    st.session_state.placed = placed
    st.session_state.boundary = boundary_polygon

# ==================== 显示结果 ====================
if 'placed' in st.session_state:
    placed = st.session_state.placed
    boundary = st.session_state.boundary
    
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_aspect('equal')
    
    # 底图
    if uploaded_image:
        img = Image.open(uploaded_image)
        # 假设底图比例匹配边界，简单缩放
        ax.imshow(img, extent=[min(p[0] for p in boundary), max(p[0] for p in boundary),
                               min(p[1] for p in boundary), max(p[1] for p in boundary)], alpha=0.3)
    
    # 边界
    boundary_patch = patches.Polygon(boundary, closed=True, fill=False, edgecolor='red', linewidth=2)
    ax.add_patch(boundary_patch)
    
    # 场地
    for i, (x, y, w, h, typ, rot) in enumerate(placed):
        rect = patches.Rectangle((x, y), w, h, facecolor=colors[typ], alpha=0.7, edgecolor='black', linewidth=1)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, f"{typ[:4]}\n{w:.0f}x{h:.0f}", ha='center', va='center', color='white', fontsize=9)
    
    min_x = min(p[0] for p in boundary) - 10
    max_x = max(p[0] for p in boundary) + 10
    min_y = min(p[1] for p in boundary) - 10
    max_y = max(p[1] for p in boundary) + 10
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.set_xlabel("东-西 (m)")
    ax.set_ylabel("南-北 (m)")
    ax.set_title(f"生成布局 (共 {len(placed)} 个场地)")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)
    
    # ==================== 导出 ====================
    col1, col2 = st.columns(2)
    
    # PNG
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
    img_buffer.seek(0)
    col1.download_button("📥 下载 PNG", img_buffer, "布局.png", "image/png")
    
    # DXF
    try:
        doc = ezdxf.new('R2010')
        doc.units = units.M
        msp = doc.modelspace()
        # 边界
        msp.add_lwpolyline(boundary)
        # 场地
        for x, y, w, h, typ, _ in placed:
            pts = [(x,y), (x+w,y), (x+w,y+h), (x,y+h), (x,y)]
            msp.add_lwpolyline(pts)
            msp.add_text(typ, dxfattribs={'height': 2}).set_pos((x + w/2, y + h/2), align='MIDDLE_CENTER')
        dxf_buffer = io.BytesIO()
        doc.saveas(dxf_buffer)
        dxf_buffer.seek(0)
        col2.download_button("📥 导出 DXF (CAD)", dxf_buffer, "布局.dxf", "application/dxf")
    except Exception as e:
        st.error(f"DXF导出失败: {e}")

st.caption("✨ 由 Grok 驱动 | 如有bug，随时反馈！")