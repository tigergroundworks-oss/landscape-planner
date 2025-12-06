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
# ==================== 读取DXF边界（完美兼容Streamlit上传） ====================
boundary_polygon = [(0,0), (width,0), (width,height), (0,height), (0,0)]

if uploaded_dxf:
    try:
        # 关键修复：先把上传的文件保存到临时路径
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_dxf.getvalue())
            tmp_path = tmp_file.name
        
        # 现在用真实路径读取
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()
        points = []
        
        # 优先找 LWPOLYLINE（最常用）
        for e in msp.query("LWPOLYLINE"):
            pts = [(p[0]*import_factor, p[1]*import_factor) for p in e.get_points("xy")]
            if len(pts) > 2:
                points = pts
                break
        
        # 如果没找到，再尝试 POLYLINE 或其他
        if not points:
            for e in msp:
                if e.dxftype() in ["POLYLINE", "LINE", "CIRCLE", "ARC"]:
                    # 简单取包围盒作为备用
                    bounds = e.bounds()
                    if bounds:
                        minx, miny, _, _ = bounds[0]
                        maxx, maxy, _, _ = bounds[1]
                        points = [(minx*import_factor, miny*import_factor),
                                  (maxx*import_factor, miny*import_factor),
                                  (maxx*import_factor, maxy*import_factor),
                                  (minx*import_factor, maxy*import_factor)]
                        break
        
        if points:
            boundary_polygon = points + [points[0]]  # 闭合
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            new_width = max(xs) - min(xs)
            new_height = max(ys) - min(ys)
            if new_width > 10 and new_height > 10:  # 防止误读
                width = new_width
                height = new_height
                st.success(f"DXF 导入成功！自动识别场地尺寸：{width:.1f}×{height:.1f} m")
            else:
                st.warning("DXF 边界太小，使用手动尺寸")
        else:
            st.warning("未识别到有效边界，使用矩形场地")
            
    except Exception as e:
        st.error(f"DXF 读取失败（常见于文件损坏或加密）：{e}")
    finally:
        # 清理临时文件
        import os
        if 'tmp_path' in locals():
            try: os.unlink(tmp_path)
            except: pass
