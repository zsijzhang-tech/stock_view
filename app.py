import streamlit as st
import pandas as pd
import requests
import time
import pytz
from datetime import datetime

# 1. 页面配置
st.set_page_config(
    page_title="实时行情监控",
    page_icon="📈",
    layout="wide"
)

# 2. 注入 CSS 样式 (缩小字体，让页面更紧凑)
st.markdown("""
<style>
    /* 缩小表格表头和内容 */
    div[data-testid="stDataFrame"] th { font-size: 14px !important; }
    div[data-testid="stDataFrame"] td { font-size: 14px !important; }
    /* 调整 Metric 组件 (大盘指数) 的字体 */
    div[data-testid="stMetricValue"] { font-size: 24px !important; }
</style>
""", unsafe_allow_html=True)

# --- 核心函数：获取股票数据 ---
def get_stock_data(codes):
    if not codes:
        return pd.DataFrame()

    # 1. 智能识别前缀
    api_codes = []
    code_map = {} 

    for code in codes:
        code = str(code).strip()
        if not code: continue

        # 如果自带前缀 (sh/sz/bj/rt_hk)
        if code.startswith(('sh', 'sz', 'bj', 'rt_hk')):
            final_code = code
        else:
            # 自动补全前缀
            if code[0] in ['5', '6', '9']:
                final_code = f"sh{code}"
            elif code[0] in ['0', '1', '2', '3']:
                final_code = f"sz{code}"
            elif code[0] in ['4', '8']:
                final_code = f"bj{code}"
            else:
                final_code = f"sh{code}" # 默认

        api_codes.append(final_code)
        code_map[final_code] = code 

    # 2. 请求数据
    url = f"http://hq.sinajs.cn/list={','.join(api_codes)}"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        text = response.content.decode('gbk')
    except Exception as e:
        st.error(f"网络请求失败: {e}")
        return pd.DataFrame()

    # 3. 解析数据
    data_list = []
    lines = text.split('\n')
    
    for line in lines:
        if not line.strip(): continue
            
        try:
            eq_split = line.split('=')
            if len(eq_split) < 2: continue
            
            # 提取 API code key
            raw_key = eq_split[0].split('_')[-1] # 默认取最后一段
            # 特殊处理港股 key (例如 rt_hkHSTECH)
            if "rt_hk" in eq_split[0]:
                raw_key = "rt_" + eq_split[0].split('_rt_')[-1]

            content = eq_split[1].strip('"')
            if not content: continue 
            
            fields = content.split(',')
            
            # === 分支处理：港股 vs A股 ===
            # 初始化变量
            name = ""
            current_price = 0.0
            pre_close = 0.0
            open_price = 0.0
            high_price = 0.0
            low_price = 0.0
            update_time = ""

            if "rt_hk" in line:
                # --- 港股/恒生指数解析 ---
                if len(fields) < 7: continue
                name = fields[1] # 中文名
                open_price = float(fields[2])
                pre_close = float(fields[3])
                high_price = float(fields[4])
                low_price = float(fields[5])
                current_price = float(fields[6])
                # 港股时间在字段 18 (或者17)
                update_time = fields[18] if len(fields) > 18 else datetime.now().strftime("%H:%M:%S")
                
            else:
                # --- A股解析 ---
                if len(fields) < 6: continue
                name = fields[0]
                open_price = float(fields[1])
                pre_close = float(fields[2])
                current_price = float(fields[3])
                high_price = float(fields[4])
                low_price = float(fields[5])
                # A股时间在字段 31
                update_time = fields[31] if len(fields) > 31 else fields[30]

            # 统一计算涨跌
            if pre_close > 0 and current_price > 0:
                change_pct = ((current_price - pre_close) / pre_close) * 100
                change_amt = current_price - pre_close
            elif pre_close > 0 and current_price == 0: 
                change_pct = 0.0
                change_amt = 0.0
                current_price = pre_close
            else:
                change_pct = 0.0
                change_amt = 0.0

            # 找回原始代码
            original_code = code_map.get(raw_key, raw_key.replace("sh","").replace("sz",""))
            # 如果是恒生科技，美化显示一下
            if "HSTECH" in str(original_code):
                original_code = "HK.Tech"

            data_list.append({
                "代码": original_code,
                "名称": name,
                "当前价": current_price,
                "涨跌额": change_amt,
                "涨跌幅(%)": change_pct,
                "开盘价": open_price,
                "最高价": high_price,
                "最低价": low_price,
                "昨收价": pre_close,
                "更新时间": update_time
            })
        except Exception:
            continue
            
    return pd.DataFrame(data_list)

# --- 样式函数 ---
def color_change(val):
    if val > 0: return 'color: #d62728' # 红
    elif val < 0: return 'color: #2ca02c' # 绿
    return 'color: black'

# --- 页面逻辑 ---

# 顶部时间显示
beijing_tz = pytz.timezone('Asia/Shanghai')
current_time = datetime.now(beijing_tz).strftime('%H:%M:%S')
st.caption(f"最后刷新: {current_time}")

# === 第一部分：大盘指数 ===
st.markdown("##### 📊 核心指数")
# 代码: 上证, 深成, 创业板, 恒生科技
index_codes = ['sh000001', 'sz399001', 'sz399006', 'rt_hkHSTECH'] 
df_index = get_stock_data(index_codes)

if not df_index.empty:
    cols = st.columns(4) # 改为4列
    for i, code in enumerate(index_codes):
        # 查找对应数据
        row = None
        for _, r in df_index.iterrows():
            # 兼容匹配逻辑
            raw_c = code.replace("sh","").replace("sz","").replace("rt_hk","")
            if raw_c in r['代码'] or (code == "rt_hkHSTECH" and "Tech" in r['代码']):
                row = r
                break
        
        if row is not None:
            with cols[i]:
                st.metric(
                    label=row['名称'],
                    value=f"{row['当前价']:.2f}",
                    delta=f"{row['涨跌额']:.2f} ({row['涨跌幅(%)']:.2f}%)",
                    delta_color="inverse"
                )
else:
    st.warning("正在获取指数数据...")

st.divider()

# === 第二部分：自选股列表 ===
st.markdown("##### 📋 自选监控")

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

with st.sidebar:
    st.header("自选管理")
    new_code = st.text_input("输入6位代码", max_chars=6)
    if st.button("添加"):
        if new_code and len(new_code) == 6:
            if new_code not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_code)
                st.rerun()
            else:
                st.warning("已在列表中")
    
    if st.session_state.watchlist:
        st.write("---")
        to_remove = st.multiselect("移除", st.session_state.watchlist)
        if st.button("确认移除"):
            for c in to_remove:
                if c in st.session_state.watchlist: st.session_state.watchlist.remove(c)
            st.rerun()

if st.session_state.watchlist:
    df_stocks = get_stock_data(st.session_state.watchlist)
    if not df_stocks.empty:
        # 调整了列顺序，去掉了"代码"列(如果想看可以加回来)，让表格更宽敞
        display_cols = ["代码", "名称", "当前价", "涨跌幅(%)", "涨跌额", "昨收价", "最高价", "最低价", "更新时间"]
        styled_df = df_stocks[display_cols].style.map(color_change, subset=['涨跌幅(%)', '涨跌额']) \
                             .format({"当前价": "{:.2f}", "涨跌幅(%)": "{:+.2f}", "涨跌额": "{:+.2f}", 
                                      "昨收价": "{:.2f}", "最高价": "{:.2f}", "最低价": "{:.2f}"})
        st.dataframe(styled_df, width="stretch", hide_index=True)
    else:
        st.info("暂无数据")
else:
    st.info("请在侧边栏添加股票")

# 自动刷新
time.sleep(10)
st.rerun()
