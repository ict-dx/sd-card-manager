import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import os

# データベースディレクトリの作成
os.makedirs('data', exist_ok=True)

# データベース接続の設定
def get_db_connection():
    conn = sqlite3.connect('data/database.db', check_same_thread=False)
    return conn

# データベースの初期化
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # SDカードテーブル
    c.execute('''
        CREATE TABLE IF NOT EXISTS sdcards
        (id INTEGER PRIMARY KEY,
         card_number TEXT UNIQUE,
         card_index INTEGER,
         status TEXT,
         capacity TEXT,
         checkout_date TIMESTAMP NULL,
         user_name TEXT NULL,
         equipment TEXT NULL,
         case_number TEXT,
         shoot_content TEXT NULL)
    ''')
    
    conn.commit()
    conn.close()

# 初期データの投入
def insert_initial_data():
    conn = get_db_connection()
    c = conn.cursor()
    
    # SDカードが存在しない場合のみ初期データを投入
    c.execute('SELECT COUNT(*) FROM sdcards')
    if c.fetchone()[0] == 0:
        # SDカード1
        card_numbers = list(range(1, 41))  # 1から40まで
        capacities = []
        for num in card_numbers:
            if 1 <= num <= 11:
                capacities.append('32G')
            elif 12 <= num <= 18:
                capacities.append('64G')
            elif 19 <= num <= 40:
                capacities.append('128G')
        
        for num, capacity in zip(card_numbers, capacities):
            card_number = f"SD1-{num}"
            c.execute('''
                INSERT INTO sdcards (card_number, card_index, status, capacity, case_number)
                VALUES (?, ?, '在庫あり', ?, 'SDカード1')
            ''', (card_number, num, capacity))
        
        # SDカード2（容量は仮に全て64Gとします）
        for num in range(1, 41):
            card_number = f"SD2-{num}"
            c.execute('''
                INSERT INTO sdcards (card_number, card_index, status, capacity, case_number)
                VALUES (?, ?, '在庫あり', '64G', 'SDカード2')
            ''', (card_number, num))
        
        # マイクロSDカード（容量は仮に全て32Gとします）
        for num in range(1, 41):
            card_number = f"microSD-{num}"
            c.execute('''
                INSERT INTO sdcards (card_number, card_index, status, capacity, case_number)
                VALUES (?, ?, '在庫あり', '32G', 'マイクロSDカード')
            ''', (card_number, num))
        
    conn.commit()
    conn.close()

class SDCardApp:
    def __init__(self):
        self.conn = get_db_connection()
    
    def get_case_numbers(self):
        query = 'SELECT DISTINCT case_number FROM sdcards'
        df = pd.read_sql_query(query, self.conn)
        return df['case_number'].tolist()
    
    def get_available_cards_by_case(self, case_number):
        query = '''
            SELECT id, card_number, capacity
            FROM sdcards
            WHERE case_number = ? AND status = '在庫あり'
            ORDER BY card_index
        '''
        return pd.read_sql_query(query, self.conn, params=(case_number,))
    
    def get_checked_out_cards_by_case(self, case_number):
        query = '''
            SELECT id, card_number, capacity, user_name, equipment, shoot_content, checkout_date
            FROM sdcards
            WHERE case_number = ? AND status = '貸出中'
            ORDER BY card_index
        '''
        return pd.read_sql_query(query, self.conn, params=(case_number,))
    
    def checkout_cards(self, card_ids, user_name, equipment, shoot_content):
        c = self.conn.cursor()
        try:
            c.execute('BEGIN TRANSACTION')
            
            placeholders = ','.join('?' for _ in card_ids)
            c.execute(f'SELECT id, status FROM sdcards WHERE id IN ({placeholders})', card_ids)
            statuses = c.fetchall()
            
            unavailable_cards = [str(id) for id, status in statuses if status != '在庫あり']
            if unavailable_cards:
                c.execute('ROLLBACK')
                return False, f"以下のカードは現在貸出できません: {', '.join(unavailable_cards)}"
    
            for card_id in card_ids:
                c.execute('''
                    UPDATE sdcards
                    SET status = '貸出中',
                        checkout_date = ?,
                        user_name = ?,
                        equipment = ?,
                        shoot_content = ?
                    WHERE id = ?
                ''', (datetime.now(), user_name, equipment, shoot_content, card_id))
            
            c.execute('COMMIT')
            return True, "貸出が完了しました"
        except Exception as e:
            c.execute('ROLLBACK')
            return False, f"エラーが発生しました: {str(e)}"
    
    def return_card(self, card_id):
        c = self.conn.cursor()
        try:
            c.execute('BEGIN TRANSACTION')
            
            c.execute('SELECT status FROM sdcards WHERE id = ?', (card_id,))
            status = c.fetchone()
            if not status or status[0] != '貸出中':
                c.execute('ROLLBACK')
                return False, "このカードは返却できません"
            
            c.execute('''
                UPDATE sdcards
                SET status = '在庫あり',
                    checkout_date = NULL,
                    user_name = NULL,
                    equipment = NULL,
                    shoot_content = NULL
                WHERE id = ?
            ''', (card_id,))
            
            c.execute('COMMIT')
            return True, "返却が完了しました"
        except Exception as e:
            c.execute('ROLLBACK')
            return False, f"エラーが発生しました: {str(e)}"
    
    def get_cards_by_case(self, case_number):
        query = '''
            SELECT card_number, status, capacity, checkout_date, user_name, equipment, case_number, shoot_content
            FROM sdcards
            WHERE case_number = ?
            ORDER BY card_index
        '''
        return pd.read_sql_query(query, self.conn, params=(case_number,))

def main():
    st.set_page_config(page_title="SDカード管理システム", layout="wide")
    
    # データベースの初期化
    init_db()
    insert_initial_data()
    
    # アプリケーションのインスタンス化
    app = SDCardApp()
    
    # セッション状態の初期化
    if 'mode' not in st.session_state:
        st.session_state.mode = 'select'
    
    # モード選択画面
    if st.session_state.mode == 'select':
        st.title("SDカード管理システム")
        
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("貸出", use_container_width=True):
                st.session_state.mode = 'checkout'
                # 選択状態をリセット
                if 'checkout_info' in st.session_state:
                    del st.session_state.checkout_info
                if 'selected_cards' in st.session_state:
                    del st.session_state.selected_cards
                st.rerun()
        with col2:
            if st.button("返却", use_container_width=True):
                st.session_state.mode = 'return'
                st.rerun()
        with col3:
            if st.button("在庫一覧", use_container_width=True):
                st.session_state.mode = 'stats'
                st.rerun()
    
    # 貸出モード
    elif st.session_state.mode == 'checkout':
        st.title("SDカード貸出")
        
        with st.form("checkout_form"):
            user_name = st.text_input("使用者名")
            equipment = st.text_input("使用機材")
            case_numbers = app.get_case_numbers()
            case_number = st.selectbox(
                "カードケース番号",
                case_numbers,
                index=None,
                placeholder="ケース番号を選択してください"
            )
            shoot_content = st.text_area("取材内容")
            
            submit = st.form_submit_button("カードを選択")
            
            if submit:
                if not user_name:
                    st.error("使用者名を入力してください")
                elif not equipment:
                    st.error("使用機材を入力してください")
                elif not case_number:
                    st.error("カードケース番号を選択してください")
                else:
                    st.session_state.checkout_info = {
                        "user_name": user_name,
                        "equipment": equipment,
                        "shoot_content": shoot_content,
                        "case_number": case_number
                    }
        
        if "checkout_info" in st.session_state:
            st.subheader(f"{st.session_state.checkout_info['case_number']} の利用可能なカード")
            available_cards = app.get_available_cards_by_case(st.session_state.checkout_info['case_number'])
            
            if not available_cards.empty:
                # 選択状態を保存するためのセッション変数
                if 'selected_cards' not in st.session_state:
                    st.session_state.selected_cards = []
                
                cols_per_row = 5
                cols = st.columns(cols_per_row)
                for idx, row in available_cards.iterrows():
                    col = cols[idx % cols_per_row]
                    card_label = f"{row['card_number']} ({row['capacity']})"
                    card_id = row['id']
                    is_selected = card_id in st.session_state.selected_cards
                    checkbox = col.checkbox(card_label, value=is_selected, key=f"card_checkbox_{card_id}")
                    if checkbox and card_id not in st.session_state.selected_cards:
                        st.session_state.selected_cards.append(card_id)
                    elif not checkbox and card_id in st.session_state.selected_cards:
                        st.session_state.selected_cards.remove(card_id)
                
                if st.session_state.selected_cards:
                    st.markdown("---")
                    selected_card_numbers = available_cards[available_cards['id'].isin(st.session_state.selected_cards)]['card_number'].tolist()
                    st.markdown(f"### 選択したカード: {', '.join(selected_card_numbers)}")
                    if st.button("貸出を確定する", type="primary"):
                        success, message = app.checkout_cards(
                            st.session_state.selected_cards,
                            st.session_state.checkout_info["user_name"],
                            st.session_state.checkout_info["equipment"],
                            st.session_state.checkout_info["shoot_content"]
                        )
                        if success:
                            st.success(message)
                            # セッション状態をクリア
                            del st.session_state.checkout_info
                            del st.session_state.selected_cards
                            st.session_state.mode = 'select'
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    st.info("カードを選択してください")
            else:
                st.info("利用可能なカードがありません")
        
        if st.button("戻る"):
            st.session_state.mode = 'select'
            if "checkout_info" in st.session_state:
                del st.session_state.checkout_info
            if "selected_cards" in st.session_state:
                del st.session_state.selected_cards
            st.rerun()
    
    # 返却モード
    elif st.session_state.mode == 'return':
        st.title("SDカード返却")
        
        case_numbers = app.get_case_numbers()
        case_number = st.selectbox(
            "カードケース番号",
            case_numbers,
            index=None,
            placeholder="ケース番号を選択してください"
        )
        
        if case_number:
            checked_out_cards = app.get_checked_out_cards_by_case(case_number)
            if not checked_out_cards.empty:
                for _, card in checked_out_cards.iterrows():
                    with st.expander(f"カード番号: {card['card_number']} ({card['capacity']})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"使用者: {card['user_name']}")
                            st.write(f"使用機材: {card['equipment']}")
                        with col2:
                            st.write(f"取材内容: {card['shoot_content']}")
                            st.write(f"貸出日: {card['checkout_date'].split(' ')[0]}")
                        if st.button("返却する", key=f"return_{card['id']}"):
                            success, message = app.return_card(card['id'])
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
            else:
                st.info("返却可能なカードはありません")
        
        if st.button("戻る"):
            st.session_state.mode = 'select'
            st.rerun()
    
    # 在庫一覧モード
    elif st.session_state.mode == 'stats':
        st.title("在庫一覧")
        
        case_numbers = app.get_case_numbers()
        case_number = st.selectbox(
            "カードケース番号",
            case_numbers,
            index=None,
            placeholder="ケース番号を選択してください"
        )
        
        if case_number:
            cards_df = app.get_cards_by_case(case_number)
            cards_df['貸出日'] = cards_df['checkout_date'].apply(lambda x: x.split(' ')[0] if x else '')
            cards_df['使用者'] = cards_df['user_name'].fillna('')
            cards_df['使用機材'] = cards_df['equipment'].fillna('')
            cards_df['取材内容'] = cards_df['shoot_content'].fillna('')
            cards_df['ステータス'] = cards_df['status']
            
            display_df = cards_df[['card_number', 'ステータス', 'capacity', '貸出日', '使用者', '使用機材', 'case_number', '取材内容']]
            display_df.columns = ['SDカード番号', 'ステータス', '容量', '貸出日', '使用者', '使用機材', 'カードケース番号', '取材内容']
            st.dataframe(display_df)
        else:
            st.info("カードケース番号を選択してください")
        
        if st.button("戻る"):
            st.session_state.mode = 'select'
            st.rerun()

if __name__ == "__main__":
    main()
