import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# 设置页面配置
st.set_page_config(
    page_title="实时行情监控",
    page_icon="📈",
    layout="wide"
)


# --- 核心函数：获取股票数据 ---
def get_stock_data(codes):
    """
    获取股票或指数数据
    codes: list, 例如 ['sh000001', '600519']
    """
    if not codes:
        return pd.DataFrame()

    # 1. 智能识别前缀
    api_codes = []
    code_map = {}  # 用于映射 API 返回的 code 到原始输入

    for code in codes:
        code = str(code).strip()
        if not code: continue

        # 如果已经带有 sh/sz/bj 前缀，直接使用
        if code.startswith(('sh', 'sz', 'bj')):
            final_code = code
        else:
            # 自动补全前缀逻辑
            # 沪市: 6(主板/科创), 5(ETF/LOF), 9(B股)
            if code[0] in ['5', '6', '9']:
                final_code = f"sh{code}"
            # 深市: 0(主板), 3(创业板), 1(ETF/LOF), 2(B股)
            elif code[0] in ['0', '1', '2', '3']:
                final_code = f"sz{code}"
            # 北交所: 8, 4
            elif code[0] in ['4', '8']:
                final_code = f"bj{code}"
            else:
                final_code = f"sh{code}"  # 默认

        api_codes.append(final_code)
        # 记录映射关系，方便后续处理
        # 注意：新浪返回的key通常是 sh600519 这种格式
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
        if not line.strip():
            continue

        try:
            # 解析格式: var hq_str_sz159915="创业板ETF,..."
            eq_split = line.split('=')
            if len(eq_split) < 2: continue

            # 提取 API 用的 code (如 sh000001)
            api_code_key = eq_split[0].split('_')[-1]

            content = eq_split[1].strip('"')
            if not content: continue

            fields = content.split(',')
            if len(fields) < 5: continue  # 数据不完整

            name = fields[0]
            open_price = float(fields[1])
            pre_close = float(fields[2])
            current_price = float(fields[3])
            high_price = float(fields[4])
            low_price = float(fields[5])

            # 涨跌幅计算
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

            # 尝试找回原始输入的代码，如果找不到就用API代码
            original_code = code_map.get(api_code_key, api_code_key.replace("sh", "").replace("sz", ""))

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
                "更新时间": fields[31] if len(fields) > 31 else (fields[30] if len(fields) > 30 else "")
            })
        except Exception:
            continue

    # 按输入顺序排序（可选）
    return pd.DataFrame(data_list)


# --- 样式函数 ---
def color_change(val):
    if val > 0:
        return 'color: #d62728'  # 红色
    elif val < 0:
        return 'color: #2ca02c'  # 绿色
    return 'color: black'


# --- 页面逻辑 ---

# st.title("实时行情看板")
# st.subheader(f"最后刷新: {datetime.now().strftime('%H:%M:%S')}")

# === 第一部分：大盘指数 (固定显示) ===
st.markdown("##### 指数")
# 定义大盘代码：上证指数, 深证成指, 创业板指, 科创50
index_codes = ['sh000001', 'sz399001', 'sz399006']
df_index = get_stock_data(index_codes)

if not df_index.empty:
    cols = st.columns(len(index_codes))
    for i, row in df_index.iterrows():
        with cols[i]:
            # 设置颜色
            color = "normal"
            if row['涨跌幅(%)'] > 0: color = "normal"  # Streamlit metric 自动处理红绿，但在A股需要反过来?
            # Streamlit 的 metric delta 默认: 涨是绿，跌是红 (美股习惯)。
            # 我们可以通过 delta_color="inverse" 来反转 (涨红跌绿 - A股习惯)

            st.metric(
                label=row['名称'],
                value=f"{row['当前价']:.3f}",
                delta=f"{row['涨跌额']:.3f} ({row['涨跌幅(%)']:.3f}%)",
                delta_color="inverse"  # A股模式：红涨绿跌
            )
else:
    st.warning("正在获取大盘数据...")

st.divider()

# === 第二部分：自选股列表 ===
st.markdown("##### 自选监控")

# 初始化 Session State
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# 侧边栏
with st.sidebar:
    st.header("自选管理")

    new_code = st.text_input("输入6位代码 (如 600519)", max_chars=6)
    if st.button("添加"):
        if new_code and len(new_code) == 6:
            if new_code not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_code)
                st.success(f"已添加 {new_code}")
                st.rerun()
            else:
                st.warning("已在列表中")
        else:
            st.warning("代码格式错误")

    if st.session_state.watchlist:
        st.write("---")
        to_remove = st.multiselect("移除", st.session_state.watchlist)
        if st.button("确认移除"):
            for code in to_remove:
                if code in st.session_state.watchlist:
                    st.session_state.watchlist.remove(code)
            st.rerun()

# 展示自选股表格
if st.session_state.watchlist:
    df_stocks = get_stock_data(st.session_state.watchlist)

    if not df_stocks.empty:
        display_cols = ["代码", "名称", "当前价", "涨跌幅(%)", "涨跌额", "昨收价", "开盘价", "最高价", "最低价",
                        "更新时间"]

        # 样式处理
        styled_df = df_stocks[display_cols].style.map(color_change, subset=['涨跌幅(%)', '涨跌额']) \
            .format({"当前价": "{:.3f}", "涨跌幅(%)": "{:+.3f}", "涨跌额": "{:+.3f}",
                     "昨收价": "{:.3f}", "开盘价": "{:.3f}",
                     "最高价": "{:.3f}", "最低价": "{:.3f}"})

        st.dataframe(styled_df, width="stretch", hide_index=True)
    else:
        st.info("暂无数据")
else:
    st.info("请在左侧添加。")

# 自动刷新逻辑
refresh_rate = 10
my_bar = st.progress(0)
for percent_complete in range(100):
    time.sleep(refresh_rate / 100)
    my_bar.progress(percent_complete + 1)
st.rerun()
