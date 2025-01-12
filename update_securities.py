from supabase import create_client
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Supabase 클라이언트 초기화
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def update_past_securities_firms():
    # 1. PastStock에서 id가 240 이상인 데이터 조회
    target_stocks = supabase.table('stocks_paststock')\
        .select('id, name, stock_code')\
        .gte('id', 240)\
        .execute()
    
    target_stocks_data = target_stocks.data
    print("Target stocks:", target_stocks_data)
    
    # 2. Stock 테이블에서 동일한 종목코드를 가진 데이터 조회
    for past_stock in target_stocks_data:
        # Stock 테이블에서 매칭되는 데이터 찾기
        stock = supabase.table('stocks_stock')\
            .select('id')\
            .eq('stock_code', past_stock['stock_code'])\
            .execute()
        
        if not stock.data:
            print(f"매칭되는 Stock 없음: {past_stock['name']}")
            continue
            
        stock_id = stock.data[0]['id']
        print(f"Stock ID: {stock_id}")
        
        # 3. StockSecuritiesFirms 데이터 조회
        securities = supabase.table('stocks_stocksecuritiesfirm')\
            .select('*')\
            .eq('stock_id', stock_id)\
            .execute()
        
        if not securities.data:
            print(f"증권사 정보 없음: {past_stock['name']}")
            continue
            
        print(f"Securities data for {past_stock['name']}:", securities.data)
        
        # 4. 기존 PastStockSecuritiesFirms 데이터 삭제
        supabase.table('stocks_paststocksecuritiesfirm')\
            .delete()\
            .eq('stock_id', past_stock['id'])\
            .execute()
        
        # 5. 새로운 데이터 삽입
        for security in securities.data:
            try:
                new_past_security = {
                    'stock_id': past_stock['id'],
                    'securitiesfirm_id': security.get('securitiesfirm_id'),
                    'equality_distribution_number_per_person': security.get('equality_distribution_number_per_person'),
                    'proportional_distribution_ratio': security.get('proportional_distribution_ratio'),
                    'number_of_distributed_shares': security.get('number_of_distributed_shares'),
                    'base_time': security.get('base_time'),
                    'minimum_equal_amount': security.get('minimum_equal_amount'),
                    'minimum_equal_quantity': security.get('minimum_equal_quantity'),
                    'proportional_amount_for_one_share': security.get('proportional_amount_for_one_share'),
                    'number_of_applicants': security.get('number_of_applicants')
                }
                
                print(f"Inserting data:", new_past_security)
                
                supabase.table('stocks_paststocksecuritiesfirm')\
                    .insert(new_past_security)\
                    .execute()
                
            except Exception as e:
                print(f"데이터 삽입 중 오류 발생: {str(e)}")
                print(f"문제가 된 데이터:", security)
            
        print(f"업데이트 완료: {past_stock['name']}")

if __name__ == "__main__":
    try:
        update_past_securities_firms()
        print("모든 데이터 업데이트가 완료되었습니다.")
    except Exception as e:
        print(f"오류 발생: {str(e)}") 