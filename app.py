import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import os
from dotenv import load_dotenv
from streamlit_js_eval import streamlit_js_eval

# 환경변수 로드
load_dotenv()

# Supabase 클라이언트 초기화
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# 페이지 설정
st.set_page_config(
    page_title="IPO 데이터 대시보드",
    layout="wide",
    initial_sidebar_state="expanded"  # 모바일에서 사이드바 기본 표시
)

# CSS로 반응형 스타일 적용
st.markdown("""
    <style>
    .stDataFrame {
        width: 100%;
        max-width: 100%;
    }
    .stDataFrame > div {
        overflow-x: auto;
    }
    [data-testid="stMetricValue"] {
        white-space: nowrap;
    }
    </style>
""", unsafe_allow_html=True)

st.title("2024년 IPO 데이터 분석")

# 사이드바에 기관 경쟁률 필터 추가
st.sidebar.header("청약시 기준")
competition_rate = st.sidebar.select_slider(
    "기관 경쟁률",
    options=[0, 100, 300, 500, 1000],
    value=500
)

# 사이드바에 청약방법 필터 
st.sidebar.header("청약방법 선택")
subscription_method = st.sidebar.radio(
    "청약방법",
    ["균등배정", "비례배분"],
    index=0
)

# Supabase에서 데이터 가져오기
def load_data():
    # 2024년 이후, 시초가가 있고, 선택된 기관 경쟁률 이상인 데이터만 가져오기
    stocks_response = supabase.table('stocks_paststock') \
        .select("*") \
        .gte('listing_date', '2024-01-01') \
        .gte('initial_price', 0) \
        .gte('institutional_competition_rate', competition_rate) \
        .execute()
    
    # 주관사 정보 가져오기
    securities_response = supabase.table('stocks_paststocksecuritiesfirm') \
        .select("*") \
        .execute()
    
    # 데이터프레임 생성
    stocks_df = pd.DataFrame(stocks_response.data)
    securities_df = pd.DataFrame(securities_response.data)
    
    # 각 종목별로 가장 좋은 조건의 주관사 정보 찾기
    best_conditions = securities_df.groupby('stock_id').agg({
        'equality_distribution_number_per_person': 'max',
        'proportional_distribution_ratio': 'min'
    }).reset_index()
    
    # 주식 데이터와 주관사 정보 병합
    df = pd.merge(
        stocks_df,
        best_conditions,
        left_on='id',
        right_on='stock_id',
        how='left'
    )

    # 날짜 형식 변환
    df['listing_date'] = pd.to_datetime(df['listing_date'])
    
    # 균등 수익금 계산
    df['equality_profit'] = df['equality_distribution_number_per_person_y'] * df['profit_amount']
    
    # 비례 배정 필요 투자금 계산
    df['proportional_required_investment'] = df['proportional_distribution_ratio_y'] * df['offer_price'] / 2
    
    return df

# 데이터 로드
df = load_data()

# 비례배분 선택 시 투자금액 입력
investment_amount = 0
if subscription_method == "비례배분":
    investment_amount = st.sidebar.number_input(
        "투자금액",
        min_value=0,
        value=100_000_000,  # 1억원으로 기본값 설정
        step=1_000_000,     # 100만원 단위로 조정 가능
        format="%d"
    )
    # 투자금액을 천 단위 구분하여 표시
    st.sidebar.write(f"현재 투자금액: {investment_amount:,}원")

# 선택된 청약방법에 따라 정렬 및 차트 데이터 설정
if subscription_method == "균등배정":
    profit_column = 'equality_profit'
    profit_label = '균등 수익금 (원)'
    df = df.sort_values(['listing_date', 'equality_distribution_number_per_person_y'], 
                       ascending=[False, False])
else:
    # 비례 수익금 계산을 여기서 수행
    df['proportional_profit'] = (investment_amount / df['proportional_required_investment']) * df['profit_amount'] + df['equality_profit']
    profit_column = 'proportional_profit'
    profit_label = '비례 수익금 (원)'
    df = df.sort_values(['listing_date', 'proportional_distribution_ratio_y'], 
                       ascending=[False, True])

# 화면 크기 확인
page_width = streamlit_js_eval(js_expressions='window.innerWidth', key='WIDTH', want_output=True)

# 화면 크기에 따라 레이아웃 결정 (예: 768px를 기준으로)
if page_width and page_width > 768:
    # 큰 화면에서는 차트를 나란히 표시
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"월별 {profit_label.split(' ')[0]} 수익금")
        monthly_profits = df.groupby(df['listing_date'].dt.month)[profit_column].sum()
        fig1 = px.bar(monthly_profits, 
                      labels={'value': profit_label, 'index': '월'},
                      title=f'월별 {profit_label.split(" ")[0]} 수익금')
        
        colors = ['#99ccff' if x < 0 else '#ff9999' for x in monthly_profits.values]
        fig1.update_traces(marker_color=colors)
        fig1.update_layout(
            yaxis=dict(tickformat=","),
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader("월별 IPO 건수")
        monthly_counts = df.groupby(df['listing_date'].dt.month).size()
        fig2 = px.bar(monthly_counts,
                      labels={'value': 'IPO 건수', 'index': '월'},
                      title='월별 IPO 건수')
        fig2.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False
        )
        st.plotly_chart(fig2, use_container_width=True)
else:
    # 작은 화면에서는 탭으로 표시
    tab1, tab2 = st.tabs(["수익금 분석", "IPO 건수"])

    with tab1:
        st.subheader(f"월별 {profit_label.split(' ')[0]} 수익금")
        monthly_profits = df.groupby(df['listing_date'].dt.month)[profit_column].sum()
        fig1 = px.bar(monthly_profits, 
                      labels={'value': profit_label, 'index': '월'},
                      title=f'월별 {profit_label.split(" ")[0]} 수익금')
        
        colors = ['#99ccff' if x < 0 else '#ff9999' for x in monthly_profits.values]
        fig1.update_traces(marker_color=colors)
        fig1.update_layout(
            yaxis=dict(tickformat=","),
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False
        )
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        st.subheader("월별 IPO 건수")
        monthly_counts = df.groupby(df['listing_date'].dt.month).size()
        fig2 = px.bar(monthly_counts,
                      labels={'value': 'IPO 건수', 'index': '월'},
                      title='월별 IPO 건수')
        fig2.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False
        )
        st.plotly_chart(fig2, use_container_width=True)

# 전체 통계를 컨테이너로 감싸서 반응형으로 만들기
with st.container():
    st.subheader("전체 통계")
    cols = st.columns([1, 1, 1])  # 동일한 너비로 분할
    
    with cols[0]:
        st.metric("평균 수익률", f"{df['return_rate'].mean():.2f}%")
    with cols[1]:
        st.metric("총 상장 건수", f"{len(df)}개")
    with cols[2]:
        total_profit = df[profit_column].sum()
        st.metric(f"총 {profit_label.split(' ')[0]} 수익금", f"{total_profit:,.0f}원")

# 개별 종목 데이터 테이블
st.subheader("개별 종목 데이터")

# 데이터프레임 스타일링 함수
def color_profits(val):
    if isinstance(val, (int, float)):
        if val > 0:
            return 'color: #ff9999'  # 분홍색 (수익)
        elif val < 0:
            return 'color: #99ccff'  # 하늘색 (손실)
        else:
            return 'color: #000000'  # 0인 경우 검정색
    return ''

# 표시할 컬럼 설정 및 순서 변경
base_columns = [
    'listing_date',  # 상장일을 맨 앞으로
    'name', 
    'offer_price', 
    'initial_price', 
    'return_rate'
]

# 청약방법에 따라 추가 컬럼 설정
if subscription_method == "균등배정":
    display_columns = base_columns + [
        'equality_profit',
        'equality_distribution_number_per_person_y'  # 균등배정 관련 컬럼만 표시
    ]
else:
    display_columns = base_columns + [
        'proportional_profit',
        'proportional_distribution_ratio_y',  # 비례배분 관련 컬럼만 표시
        'proportional_required_investment'
    ]

# 데이터프레임 표시 부분 수정
try:
    # 기본 컬럼명 변환 딕셔너리
    rename_dict = {
        'listing_date': '상장일',
        'name': '종목명',
        'offer_price': '공모가',
        'initial_price': '시초가',
        'return_rate': '수익률'
    }
    
    # 청약방법에 따라 추가 컬럼명 설정
    if subscription_method == "균등배정":
        rename_dict.update({
            'equality_profit': '균등 수익금',
            'equality_distribution_number_per_person_y': '균등배정 예상수량'
        })
    else:
        rename_dict.update({
            'proportional_profit': '비례 수익금',
            'proportional_distribution_ratio_y': '비례배분 경쟁률',
            'proportional_required_investment': '비례배정 필요 투자금'
        })
    
    styled_df = df[display_columns].rename(columns=rename_dict)
    
    # 데이터 형식 지정
    styled_df = styled_df.copy()
    styled_df['상장일'] = styled_df['상장일'].dt.strftime('%Y-%m-%d')
    styled_df['수익률'] = styled_df['수익률'].round(2)
    
    if subscription_method == "균등배정":
        styled_df['균등배정 예상수량'] = styled_df['균등배정 예상수량'].round(2)
        styled_df['균등 수익금'] = styled_df['균등 수익금'].round(0)
    else:
        styled_df['비례배분 경쟁률'] = styled_df['비례배분 경쟁률'].round(2)
        styled_df['비례배정 필요 투자금'] = styled_df['비례배정 필요 투자금'].round(0)
        styled_df['비례 수익금'] = styled_df['비례 수익금'].round(0)
    
    # 숫자 형식 지정 함수
    def format_numbers(val):
        if isinstance(val, (int, float)):
            if pd.isna(val):
                return ''
            if isinstance(val, int) or val.is_integer():
                return f'{int(val):,}'
            return f'{val:.2f}'
        return val

    # 수익률과 수익금 컬럼에만 색상 스타일 적용
    style_columns = ['수익률']
    if subscription_method == "균등배정":
        style_columns.append('균등 수익금')
        format_columns = ['공모가', '시초가', '수익률', '균등배정 예상수량', '균등 수익금']
    else:
        style_columns.append('비례 수익금')
        format_columns = ['공모가', '시초가', '수익률', '비례배분 경쟁률', '비례배정 필요 투자금', '비례 수익금']
    
    # 스타일 적용
    st.dataframe(
        styled_df.style
        .map(color_profits, subset=style_columns)
        .format(format_numbers, subset=format_columns),
        hide_index=True,
        use_container_width=True,
        height=500
    )
except KeyError as e:
    st.error(f"컬럼 접근 오류: {str(e)}")
    st.write("현재 사용 가능한 컬럼:", df.columns.tolist())

