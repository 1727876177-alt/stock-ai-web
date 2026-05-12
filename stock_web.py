import os
import time
import requests
import akshare as ak
import streamlit as st
from datetime import datetime
from openai import OpenAI

# ===== 页面设置 =====
st.set_page_config(
    page_title="AI股票分析助手",
    page_icon="📈",
    layout="wide"
)

st.title("📈 AI股票分析助手")
st.caption("实时行情 + K线技术面 + 公司盈利能力 + AI综合分析")


# ===== 工具函数 =====
def get_sina_code(stock_code):
    if stock_code.startswith("6"):
        return "sh" + stock_code
    else:
        return "sz" + stock_code


def is_empty(value):
    try:
        return value is None or value != value
    except:
        return True


def format_yi(value):
    if is_empty(value):
        return "无数据"
    try:
        return f"{float(value) / 100000000:.2f}亿"
    except:
        return "无数据"


def format_number(value):
    if is_empty(value):
        return "无数据"
    try:
        return f"{float(value):.2f}"
    except:
        return "无数据"


def format_percent(value):
    if is_empty(value):
        return "无数据"
    try:
        return f"{float(value):.2f}%"
    except:
        return "无数据"


def calc_growth(current, previous):
    try:
        if is_empty(current) or is_empty(previous) or float(previous) == 0:
            return "无数据"

        growth = (float(current) - float(previous)) / abs(float(previous)) * 100
        return f"{growth:.2f}%"
    except:
        return "无数据"


def get_value(df, indicator, date_col):
    try:
        row = df[df["指标"].astype(str).str.strip() == indicator]

        if row.empty:
            return None

        value = row.iloc[0][date_col]

        if is_empty(value):
            return None

        return value
    except:
        return None


def get_value_any(df, indicators, date_col):
    for indicator in indicators:
        value = get_value(df, indicator, date_col)
        if value is not None:
            return value
    return None


def get_realtime_data(stock_code):
    sina_code = get_sina_code(stock_code)
    url = f"https://hq.sinajs.cn/list={sina_code}"
    headers = {"Referer": "https://finance.sina.com.cn"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        text = response.text
        data = text.split('"')[1].split(",")

        stock_name = data[0]
        open_price = float(data[1])
        yesterday_close = float(data[2])
        current_price = float(data[3])
        high_price = float(data[4])
        low_price = float(data[5])
        volume = int(data[8])
        amount = float(data[9])
        date = data[30]
        time_now = data[31]

        if yesterday_close != 0:
            change = current_price - yesterday_close
            change_pct = change / yesterday_close * 100
            amplitude = (high_price - low_price) / yesterday_close * 100
        else:
            change = 0
            change_pct = 0
            amplitude = 0

        amount_yi = amount / 100000000

        if high_price != low_price:
            day_position = (current_price - low_price) / (high_price - low_price) * 100
        else:
            day_position = 50

        if day_position >= 75:
            intraday_strength = "收在日内高位，短线承接较强"
        elif day_position >= 50:
            intraday_strength = "收在日内中上位置，走势尚可"
        elif day_position >= 25:
            intraday_strength = "收在日内中下位置，资金承接一般"
        else:
            intraday_strength = "收在日内低位，短线偏弱"

        realtime_info = f"""
股票名称：{stock_name}
股票代码：{stock_code}
日期时间：{date} {time_now}

开盘价：{open_price}
昨收价：{yesterday_close}
当前/收盘价：{current_price}
最高价：{high_price}
最低价：{low_price}

涨跌额：{change:.2f}
涨跌幅：{change_pct:.2f}%
振幅：{amplitude:.2f}%
成交量：{volume}
成交额：{amount_yi:.2f}亿

日内收盘位置：{day_position:.2f}%
日内强弱判断：{intraday_strength}
"""
        return stock_name, sina_code, realtime_info

    except Exception as e:
        return stock_code, sina_code, f"实时行情获取失败：{e}"


def get_kline_data(sina_code):
    try:
        hist = ak.stock_zh_a_daily(
            symbol=sina_code,
            adjust="qfq"
        )

        if hist is None or hist.empty:
            return "历史K线获取失败：返回数据为空。"

        hist = hist.tail(30).copy()

        for col in ["open", "high", "low", "close", "volume"]:
            hist[col] = hist[col].astype(float)

        hist["MA5"] = hist["close"].rolling(window=5).mean()
        hist["MA10"] = hist["close"].rolling(window=10).mean()
        hist["MA20"] = hist["close"].rolling(window=20).mean()

        latest = hist.iloc[-1]

        close_price = latest["close"]
        ma5 = latest["MA5"]
        ma10 = latest["MA10"]
        ma20 = latest["MA20"]

        latest_volume = latest["volume"]
        avg_5_volume = hist["volume"].tail(5).mean()
        avg_20_volume = hist["volume"].tail(20).mean()

        volume_ratio = latest_volume / avg_20_volume if avg_20_volume != 0 else 0

        high_20 = hist["high"].tail(20).max()
        low_20 = hist["low"].tail(20).min()

        distance_to_20_high = (close_price - high_20) / high_20 * 100 if high_20 != 0 else 0
        distance_to_20_low = (close_price - low_20) / low_20 * 100 if low_20 != 0 else 0

        if close_price > ma5 > ma10 > ma20:
            trend = "多头排列，趋势偏强"
        elif close_price < ma5 < ma10 < ma20:
            trend = "空头排列，趋势偏弱"
        elif close_price > ma20:
            trend = "价格在20日线上方，中期趋势尚可"
        else:
            trend = "价格在20日线下方，中期偏弱"

        recent_20 = hist.tail(20)[["date", "open", "high", "low", "close", "volume"]]

        kline_info = f"""
K线技术面摘要：

最新收盘价：{close_price:.2f}

MA5：{ma5:.2f}
MA10：{ma10:.2f}
MA20：{ma20:.2f}

最新成交量：{latest_volume:.0f}
近5日平均成交量：{avg_5_volume:.0f}
近20日平均成交量：{avg_20_volume:.0f}
量能倍率：{volume_ratio:.2f}倍

20日最高价：{high_20:.2f}
20日最低价：{low_20:.2f}
距离20日高点：{distance_to_20_high:.2f}%
距离20日低点：{distance_to_20_low:.2f}%

趋势判断：{trend}

最近20天K线数据：
{recent_20.to_string(index=False)}
"""
        return kline_info

    except Exception as e:
        return f"历史K线获取失败：{e}"


def get_fundamental_data(stock_code):
    try:
        df = ak.stock_financial_abstract(symbol=stock_code)

        if df.empty:
            return "财务数据为空，暂不分析基本面。"

        date_cols = list(df.columns[2:])
        latest_date = date_cols[0]

        last_year_same_date = str(int(latest_date[:4]) - 1) + latest_date[4:]

        if last_year_same_date not in date_cols:
            last_year_same_date = None

        revenue = get_value_any(df, ["营业总收入", "营业收入"], latest_date)
        net_profit = get_value_any(df, ["归母净利润", "净利润"], latest_date)
        deduct_profit = get_value_any(df, ["扣非净利润"], latest_date)
        cash_flow = get_value_any(df, ["经营现金流量净额"], latest_date)
        eps = get_value_any(df, ["基本每股收益"], latest_date)
        net_asset_per_share = get_value_any(df, ["每股净资产"], latest_date)

        roe = get_value_any(
            df,
            ["净资产收益率", "加权净资产收益率", "净资产收益率(加权)"],
            latest_date
        )

        gross_margin = get_value_any(
            df,
            ["销售毛利率", "毛利率"],
            latest_date
        )

        net_margin = get_value_any(
            df,
            ["销售净利率", "净利率"],
            latest_date
        )

        debt_ratio = get_value_any(
            df,
            ["资产负债率"],
            latest_date
        )

        if last_year_same_date:
            revenue_last_year = get_value_any(df, ["营业总收入", "营业收入"], last_year_same_date)
            net_profit_last_year = get_value_any(df, ["归母净利润", "净利润"], last_year_same_date)
            deduct_profit_last_year = get_value_any(df, ["扣非净利润"], last_year_same_date)

            revenue_yoy = calc_growth(revenue, revenue_last_year)
            net_profit_yoy = calc_growth(net_profit, net_profit_last_year)
            deduct_profit_yoy = calc_growth(deduct_profit, deduct_profit_last_year)
        else:
            revenue_yoy = "无数据"
            net_profit_yoy = "无数据"
            deduct_profit_yoy = "无数据"

        fundamental_judge = ""

        if net_profit is not None and float(net_profit) > 0:
            fundamental_judge += "公司最新报告期保持盈利；"
        else:
            fundamental_judge += "公司最新报告期盈利能力偏弱或亏损；"

        if net_profit_yoy != "无数据" and "-" not in net_profit_yoy:
            fundamental_judge += "归母净利润同比增长，业绩有改善迹象；"
        elif net_profit_yoy != "无数据":
            fundamental_judge += "归母净利润同比下滑，需要注意业绩压力；"

        if cash_flow is not None and float(cash_flow) > 0:
            fundamental_judge += "经营现金流为正，经营质量尚可。"
        else:
            fundamental_judge += "经营现金流偏弱，需要注意回款和经营质量。"

        fundamental_info = f"""
财务基本面摘要：

最新报告期：{latest_date}

【利润与收入】
营业总收入：{format_yi(revenue)}
归母净利润：{format_yi(net_profit)}
扣非净利润：{format_yi(deduct_profit)}
经营现金流量净额：{format_yi(cash_flow)}

【每股指标】
基本每股收益 EPS：{format_number(eps)}
每股净资产：{format_number(net_asset_per_share)}

【盈利能力】
ROE：{format_percent(roe)}
毛利率：{format_percent(gross_margin)}
净利率：{format_percent(net_margin)}

【财务风险】
资产负债率：{format_percent(debt_ratio)}

【同比增长】
营业收入同比：{revenue_yoy}
归母净利润同比：{net_profit_yoy}
扣非净利润同比：{deduct_profit_yoy}

【基本面初步判断】
{fundamental_judge}
"""
        return fundamental_info

    except Exception as e:
        return f"财务数据获取失败：{e}"


def analyze_one_stock(stock_code, api_key):
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    stock_name, sina_code, realtime_info = get_realtime_data(stock_code)
    kline_info = get_kline_data(sina_code)
    fundamental_info = get_fundamental_data(stock_code)

    stock_info = f"""
【实时行情】
{realtime_info}

【K线技术面】
{kline_info}

【财务基本面】
{fundamental_info}
"""

    prompt = f"""
你是A股综合分析助手，风格偏短线复盘 + 基本面筛选。

请严格基于下面的数据分析，不要编造新闻，不要编造不存在的数据。

{stock_info}

请输出：

1. 今日走势总结
2. K线趋势分析
3. 均线结构判断
4. 量能分析
5. 20日高低位位置判断
6. 公司盈利能力分析
7. 收入、净利润、扣非净利润质量
8. 经营现金流质量
9. 基本面是否支撑当前走势
10. 明日可能走势
11. 强势走势应对策略
12. 弱势走势应对策略
13. 风险提示
14. 综合结论

要求：
- 技术面看短线，基本面看质量
- 不要用基本面强行预测明天涨跌
- 不要保证股价涨跌
- 语言直接，适合普通股民阅读
- 只做辅助分析，不构成投资建议
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )

    return stock_name, stock_info, response.choices[0].message.content


# ===== 网页侧边栏 =====
st.sidebar.header("设置")

api_key = st.sidebar.text_input(
    "DeepSeek API Key",
    type="password",
    placeholder="请输入 sk- 开头的 API Key"
)

st.sidebar.caption("你的 Key 只在本地运行时使用，不会保存到代码里。")

stock_input = st.text_input(
    "请输入股票代码，多个用逗号隔开",
    value="002757,601138,002463"
)

analyze_button = st.button("开始分析", type="primary")

# ===== 主页面 =====
if analyze_button:
    if not api_key:
        st.error("请先在左侧输入 DeepSeek API Key")
        st.stop()

    stock_codes = stock_input.replace("，", ",").split(",")

    report_content = []

    for code in stock_codes:
        code = code.strip()

        if code == "":
            continue

        st.divider()
        st.subheader(f"正在分析：{code}")

        with st.spinner(f"{code} 分析中，请稍等..."):
            try:
                stock_name, stock_info, ai_result = analyze_one_stock(code, api_key)

                st.success(f"{stock_name}（{code}）分析完成")

                with st.expander("查看输入给 AI 的原始数据"):
                    st.text(stock_info)

                st.markdown("### AI 综合分析结果")
                st.write(ai_result)

                one_report = f"""
============================================================
股票：{stock_name}（{code}）
============================================================

【输入给AI的数据】
{stock_info}

【AI综合分析结果】
{ai_result}

"""
                report_content.append(one_report)

                time.sleep(1)

            except Exception as e:
                st.error(f"{code} 分析失败：{e}")
                report_content.append(f"{code} 分析失败：{e}")

    if report_content:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_text = "\n".join(report_content)

        st.download_button(
            label="下载本次分析报告 TXT",
            data=report_text,
            file_name=f"stock_report_{now}.txt",
            mime="text/plain"
        )