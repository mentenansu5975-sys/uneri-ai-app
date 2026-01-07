import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import datetime
import time

# --- 1. ページ基本設定 ---
st.set_page_config(page_title="AI相場師・究極完全版", layout="wide")

# スタイル（和風・職人風の見た目）
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; }
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 10px; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 師匠たちの「教え込み」定義 ---
THEORY_TEXT = """
【林輝太郎流：うねり取りの極意】
- 予測を排し、値動きに対する「玉の操作」に徹せよ。
- 6ヶ月から2年の「うねり」を月足で捉えよ。
- 1-2-3の分割売買を徹底し、決して一度に全額投入するな。

【相場師朗流：ショットガン・うねり取り】
- 移動平均線の並び（パンパカパン等）と傾きを重視せよ。
- 「下半身・逆下半身」のサインを見逃すな。
- 7の法則：一つのトレンドは概ね7本（日/週/月）で一段落する。
"""

# --- 3. セッション状態の初期化（場帳データ保持用） ---
if 'bacho_data' not in st.session_state:
    st.session_state.bacho_data = pd.DataFrame(columns=['日付', '銘柄', '終値', '玉(L-S)', '備考'])

# --- 4. サイドバー：銘柄と玉操作設定 ---
with st.sidebar:
    st.header("🎛️ 相場師の道具箱")
    api_key = st.secrets["GEMINI_API_KEY"]
    ticker = st.text_input("銘柄コード", value="9101.T")
    
    st.divider()
    st.subheader("📊 現在の持玉（ポジション）")
    col1, col2 = st.columns(2)
    long_q = col1.number_input("買い数", value=0, step=100)
    short_q = col2.number_input("売り数", value=0, step=100)
    
    st.divider()
    st.subheader("💰 証拠金シミュレーター")
    leverage = st.slider("レバレッジ（倍）", 1, 3, 3)
    capital = st.number_input("運用資金 (円)", value=1000000)

# --- 5. メイン画面：データ取得と表示 ---
st.title("🌊 AI相場師・究極完全版")
st.caption("林輝太郎・相場師朗 理論継承アプリ")

stock = yf.Ticker(ticker)
# 期間切り替えボタン（日・週・月）
time_unit = st.radio("表示周期を選択", ["日足", "週足", "月足"], horizontal=True, index=2)
period_map = {"日足": "1y", "週足": "5y", "月足": "max"}
resample_map = {"日足": "D", "週足": "W", "月足": "M"}

hist = stock.history(period=period_map[time_unit])
df = hist.resample(resample_map[time_unit]).last().dropna()

if not df.empty:
    current_price = df['Close'].iloc[-1]
    
    # 指標表示
    m1, m2, m3 = st.columns(3)
    m1.metric("現在値", f"{current_price:,.1f}円")
    m2.metric("玉比率 (L-S)", f"{long_q} - {short_q}")
    
    # 証拠金計算
    total_val = (long_q + short_q) * current_price
    required_margin = total_val / leverage
    margin_ratio = (capital / required_margin * 100) if required_margin > 0 else 100
    m3.metric("証拠金維持率", f"{margin_ratio:.1f}%", delta=f"必要: {required_margin:,.0f}円", delta_color="inverse")

    # チャート
    st.subheader(f"📈 {time_unit}チャート")
    st.line_chart(df['Close'])

    # --- 6. デジタル場帳機能 ---
    st.divider()
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("📓 今日の場帳記入")
        with st.form("bacho_form"):
            note = st.text_input("備考（相場のリズム感など）")
            if st.form_submit_button("場帳に記帳"):
                new_entry = {
                    '日付': datetime.date.today(),
                    '銘柄': ticker,
                    '終値': current_price,
                    '玉(L-S)': f"{long_q}-{short_q}",
                    '備考': note
                }
                st.session_state.bacho_data = pd.concat([st.session_state.bacho_data, pd.DataFrame([new_entry])], ignore_index=True)
                st.success("記帳しました")

    with col_b:
        st.subheader("📋 過去の記帳履歴")
        st.dataframe(st.session_state.bacho_data.tail(10), use_container_width=True)
        if not st.session_state.bacho_data.empty:
            st.download_button("場帳をCSVで保存", st.session_state.bacho_data.to_csv(index=False).encode('utf_8_sig'), "bacho.csv")

    # --- 7. AI相場師・戦略診断 ---
    st.divider()
    if st.button("🤖 師匠AIに玉操作を相談する"):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        あなたは林輝太郎と相場師朗の理論を極めた投資顧問です。
        {THEORY_TEXT}
        
        現在のデータ：
        - 周期：{time_unit}
        - 現在値：{current_price}円
        - 過去の最高値：{df['Close'].max():,.0f}円
        - 過去の最安値：{df['Close'].min():,.0f}円
        - ユーザーの玉：買い{long_q}、売り{short_q}
        - 維持率：{margin_ratio:.1f}%
        
        指示：
        1. 今の価格位置が「うねり」のどの段階か判定せよ。
        2. 分割売買の観点から、次の一手を「2-0から2-2へ」などの形式で助言せよ。
        3. 相場師朗流の「7の法則」や移動平均線を意識した一言を添えよ。
        """
        with st.spinner('相場を観測中...'):
            response = model.generate_content(prompt)
            st.info(response.text)

else:
    st.error("データが取得できません。")
