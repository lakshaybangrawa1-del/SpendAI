import os
import streamlit as st
from dotenv import load_dotenv
from Core.scanner import scan_receipt
from Database.db_manager import add_expense, get_all_expenses, init_db
import pandas as pd
import base64
import plotly.express as px
import sqlite3
import re
import hashlib
import datetime
from streamlit_mic_recorder import speech_to_text

load_dotenv()

st.set_page_config(page_title="SpendAI Secure", layout="wide", initial_sidebar_state="collapsed")

def init_auth_db():
    conn = sqlite3.connect("spendai.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN username TEXT DEFAULT 'guest'")
    except sqlite3.OperationalError:
        pass 
    conn.commit()
    conn.close()

init_db()
init_auth_db()

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_user_db(username, password):
    conn = sqlite3.connect("spendai.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    data = cursor.fetchone()
    conn.close()
    if data and data[0] == make_hashes(password):
        return True
    return False

def register_user_db(username, password):
    conn = sqlite3.connect("spendai.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?,?)", (username, make_hashes(password)))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def purge_agent_complete(username):
    try:
        conn = sqlite3.connect("spendai.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE username = ?", (username,))
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_user_expenses(username):
    conn = sqlite3.connect("spendai.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, amount, category, description, date, source FROM expenses WHERE username = ?", (username,))
    data = cursor.fetchall()
    conn.close()
    return data

def add_user_expense(amount, category, description, date, source, username):
    conn = sqlite3.connect("spendai.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (amount, category, description, date, source, username) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (amount, category, description, date, source, username))
    conn.commit()
    conn.close()

def delete_expense_inline(expense_id, username):
    try:
        conn = sqlite3.connect("spendai.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE id = ? AND username = ?", (expense_id, username))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def parse_banking_sms(sms_text):
    sms_text_lower = sms_text.lower()
    amount_match = re.search(r'(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)', sms_text_lower)
    amount = 0.0
    if amount_match:
        amount = float(amount_match.group(1).replace(',', ''))
    vendor_match = re.search(r'(?:to|at|vpa)\s+([a-zA-Z0-9\s\.\@\-]+?)(?:\s+on|\s+via|\s+balance|\.|$)', sms_text_lower)
    description = "Automated SMS Log"
    if vendor_match:
        description = f"UPI: {vendor_match.group(1).strip().upper()}"
    categories = {
        'food': ['swiggy', 'zomato', 'restaurant', 'dhaba', 'kfc', 'mcd'],
        'fuel': ['pump', 'petroleum', 'hpcl', 'bpcl', 'iocl', 'fuel'],
        'shopping': ['amazon', 'flipkart', 'myntra', 'blinkit', 'zepto'],
        'travel': ['uber', 'ola', 'rapido', 'irctc', 'metro']
    }
    detected_cat = "Other"
    for cat, keywords in categories.items():
        if any(kw in sms_text_lower for kw in keywords):
            detected_cat = cat.capitalize()
            break
    return {
        'amount': amount,
        'category': detected_cat,
        'description': description,
        'date': pd.Timestamp.now().strftime('%Y-%m-%d')
    }

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

bg_image_path = "background.png" 
base64_string = get_base64_image(bg_image_path) if os.path.exists(bg_image_path) else ""

css_style = """
    <style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #020617 100%) !important;
        color: #f8fafc !important;
        font-family: 'Inter', sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 15px;
        background: rgba(30, 41, 59, 0.45);
        backdrop-filter: blur(12px);
        padding: 10px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94a3b8 !important;
        font-weight: 700;
        padding: 10px 25px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%) !important;
        color: #FFFFFF !important;
        border-radius: 8px;
    }
    section[data-testid="stFileUploader"] {
        background: rgba(30, 41, 59, 0.35);
        border: 2px dashed #38bdf8 !important;
        border-radius: 16px;
        padding: 25px;
    }
    .stDataFrame, div[data-testid="stMetricValue"], .metric-card, .auth-container {
        background: rgba(30, 41, 59, 0.45) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px;
        padding: 20px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #38bdf8 !important;
    }
    .stButton>button {
        background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%) !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        width: 100%;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 0 !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
    }
    .stDownloadButton>button {
        background: linear-gradient(135deg, #60A5FA 0%, #2563EB 100%) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        width: 100%;
        border: none !important;
        border-radius: 10px !important;
        padding: 10px 0 !important;
    }
    .delete-btn>button {
        background: linear-gradient(135deg, #EF4444 0%, #B91C1C 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
    }
    .speech-box {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid #38bdf8;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 20px;
        text-align: center;
    }
    .dashboard-title h2 {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #ffffff !important;
        margin: 0 !important;
    }
    </style>
"""

st.markdown(css_style, unsafe_allow_html=True)

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""

def parse_voice_text(text):
    text = text.lower()
    numbers = re.findall(r'\d+', text)
    amount = float(numbers[0]) if numbers else 0.0
    categories = ['food', 'fuel', 'rent', 'shopping', 'entertainment', 'travel', 'bills']
    found_cat = 'Other'
    for c in categories:
        if c in text:
            found_cat = c.capitalize()
            break
    return {
        'amount': amount, 'category': found_cat,
        'description': text.replace(str(int(amount)), "").strip() if amount else text,
        'date': pd.Timestamp.now().strftime('%Y-%m-%d')
    }

def show_welcome_banner(username):
    current_hour = datetime.datetime.now().hour
    if current_hour < 12:
        greeting = "Good Morning ☀️"
    elif current_hour < 17:
        greeting = "Good Afternoon 🌤️"
    else:
        greeting = "Good Evening 🌙"
        
    st.markdown(f"""
        <div style="background: linear-gradient(90deg, rgba(37,99,235,0.2) 0%, rgba(56,189,248,0.05) 100%); 
                    padding: 15px; border-left: 5px solid #38bdf8; border-radius: 8px; margin-bottom: 20px;">
            <p style="margin: 0; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 2px; color: #94a3b8;">
                {greeting}
            </p>
            <h1 style="margin: 3px 0 0 0; font-size: 1.8rem; font-weight: 800; color: #ffffff;">
                Welcome Back, <span style="color: #38bdf8;">{username}</span>!
            </h1>
        </div>
    """, unsafe_allow_html=True)

if not st.session_state['authenticated']:
    st.title("🔒 SpendAI Security Gate")
    
    col_a1, col_a2, col_a3 = st.columns([1, 2, 1])
    with col_a2:
        st.markdown('<div class="auth-container">', unsafe_allow_html=True)
        auth_mode = st.radio("Access Protocol", ["Login Existing Matrix", "Register New Ledger Agent"])
        
        username_input = st.text_input("User Tag ID")
        password_input = st.text_input("Security Matrix Key", type="password")
        
        if auth_mode == "Login Existing Matrix":
            if st.button("Authorize Access"):
                if check_user_db(username_input, password_input):
                    st.session_state['authenticated'] = True
                    st.session_state['username'] = username_input
                    st.success(f"Access Granted. Greeting Agent {username_input}.")
                    st.rerun()
                else:
                    st.error("Invalid Credentials Layer Mismatch.")
        else:
            if st.button("Initialize Agent Registration"):
                if username_input and password_input:
                    if register_user_db(username_input, password_input):
                        st.success("Registration Successful! Please switch to Login.")
                    else:
                        st.error("Username already bound in ledger.")
                else:
                    st.warning("Input parameters cannot be null.")
        st.markdown('</div>', unsafe_allow_html=True)

else:
    current_user = st.session_state['username']
    
    show_welcome_banner(current_user)
    
    col_h1, col_h2 = st.columns([7, 5])
    with col_h1:
        st.markdown(f'<div class="dashboard-title"><h2>📊 SpendAI Dashboard — {current_user}</h2></div>', unsafe_allow_html=True)
    with col_h2:
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
            if st.button("🗑️ Delete Account"):
                if purge_agent_complete(current_user):
                    st.session_state['authenticated'] = False
                    st.session_state['username'] = ""
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with col_btn2:
            if st.button("🚪 Logout"):
                st.session_state['authenticated'] = False
                st.session_state['username'] = ""
                st.rerun()

    st.write("---")
    
    user_expenses = get_user_expenses(current_user)
    df = pd.DataFrame(user_expenses, columns=['ID', 'Amount', 'Category', 'Description', 'Date', 'Source'])
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'])
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        budget_limit = st.number_input("Set Monthly Budget Limit (₹)", value=15000.0, step=1000.0)
    with col_c2:
        min_date = df['Date'].min().date() if not df.empty else pd.Timestamp.now().date()
        max_date = df['Date'].max().date() if not df.empty else pd.Timestamp.now().date()
        date_range = st.date_input("Filter Timeline Range", value=(min_date, max_date))
        if isinstance(date_range, tuple) and len(date_range) == 2 and not df.empty:
            start_date, end_date = date_range
            df = df[(df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)]

    if not df.empty:
        total_spend = df['Amount'].sum()
        m1, m2, m3 = st.columns(3)
        with m1: st.metric(label="Ledger Burn", value=f"₹{total_spend:,.2f}")
        with m2:
            try: top_category = df.groupby('Category')['Amount'].sum().idxmax()
            except: top_category = "N/A"
            st.metric(label="Highest Category", value=str(top_category))
        with m3: st.metric(label="Logged Streams", value=str(len(df)))
        
        if total_spend > budget_limit: st.error(f"CRITICAL OVERBURN: Budget limit broken by ₹{total_spend - budget_limit:,.2f}!")
        else: st.success(f"SAFE ZONE: ₹{budget_limit - total_spend:,.2f} remaining inside limit.")
        st.progress(min(total_spend / budget_limit, 1.0))

    st.write("---")

    tab1, tab2, tab3 = st.tabs(["📥 Scan & Voice Input", "📱 SMS Telemetry Simulator", "📈 Dashboard Matrix"])

    with tab1:
        col_mode1, col_mode2 = st.columns([1, 1])
        
        with col_mode1:
            st.subheader("📷 Image Scanner Engine")
            uploaded_file = st.file_uploader("Upload Bill/Invoice", type=["jpg", "jpeg", "png"], key="uploader_matrix")
            
            if uploaded_file is not None:
                st.image(uploaded_file, width=280)
                if 'scanned_data' not in st.session_state:
                    if st.button("Confirm & File Transaction"):
                        with st.spinner("AI Scanning..."):
                            temp_path = f"temp_{uploaded_file.name}"
                            with open(temp_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            try:
                                data = scan_receipt(temp_path)
                                if data and isinstance(data, dict):
                                    st.session_state['scanned_data'] = data
                                else:
                                    st.warning("AI Engine failed. Using Fallback System.")
                                    st.session_state['scanned_data'] = {'amount': 0.0, 'category': '', 'description': '', 'date': pd.Timestamp.now().strftime('%Y-%m-%d')}
                            except:
                                st.session_state['scanned_data'] = {'amount': 0.0, 'category': '', 'description': '', 'date': pd.Timestamp.now().strftime('%Y-%m-%d')}
                            finally:
                                try:
                                    if os.path.exists(temp_path):
                                        os.remove(temp_path)
                                except:
                                    pass
        
        with col_mode2:
            st.subheader("🎙️ Voice Ledger Engine")
            st.write("Click below and say: *'Spent 450 rupees on food today'*")
            
            text_from_voice = speech_to_text(start_prompt="🔴 Start Recording", stop_prompt="⏹️ Stop & Process", just_once=True, key='voice_input')
            
            if text_from_voice:
                st.markdown(f'<div class="speech-box">🗣️ <b>Heard:</b> <i>"{text_from_voice}"</i></div>', unsafe_allow_html=True)
                if 'scanned_data' not in st.session_state:
                    parsed_voice = parse_voice_text(text_from_voice)
                    st.session_state['scanned_data'] = parsed_voice

        if 'scanned_data' in st.session_state:
            data = st.session_state['scanned_data']
            st.write("---")
            st.subheader("📝 Verify Transaction Ledger Matrix")
            
            try: val_amt = float(data.get('amount', 0.0))
            except: val_amt = 0.0
                
            amount = st.number_input("Amount", value=val_amt, format="%.2f")
            category = st.text_input("Category", value=data.get('category', ''))
            description = st.text_input("Description", value=data.get('description', ''))
            try: val_date = pd.to_datetime(data.get('date', pd.Timestamp.now()))
            except: val_date = pd.Timestamp.now()
            date = st.date_input("Date", value=val_date)
            
            col_save1, col_save2 = st.columns([1, 4])
            with col_save1:
                if st.button("Save Entry"):
                    add_user_expense(amount=amount, category=category, description=description, date=date.strftime("%Y-%m-%d"), source='Voice/Scan', username=current_user)
                    st.success("Logged into Matrix!")
                    del st.session_state['scanned_data']
                    if 'uploader_matrix' in st.session_state:
                        del st.session_state['uploader_matrix']
                    st.rerun()
            with col_save2:
                if st.button("❌ Clear/Cancel Form"):
                    del st.session_state['scanned_data']
                    if 'uploader_matrix' in st.session_state:
                        del st.session_state['uploader_matrix']
                    st.rerun()

    with tab2:
        st.subheader("📱 Bank Transaction SMS Parsing Engine (Android Emulator)")
        st.write("Paste an official bank transaction alert format text to trigger automated script extraction:")
        
        sample_sms = "Dear Customer, A/C X0471 Debited by ₹2,500.00 on 2026-06-21 via UPI to ZOMATO. Ref No: 819533."
        sms_input = st.text_area("Paste Transaction SMS Body Here", value=sample_sms, height=120)
        
        if st.button("Execute Automatic SMS Extraction & Sync"):
            if sms_input:
                with st.spinner("Compiling Token String Vectors..."):
                    parsed_sms = parse_banking_sms(sms_input)
                    st.session_state['scanned_data'] = parsed_sms
                    st.success("Regex extraction complete! Redirected parameters to validation frame.")
                    st.rerun()

    with tab3:
        if not df.empty:
            col1, col2 = st.columns([1.2, 0.8])
            with col1:
                st.subheader("Filtered History Stream")
                display_df = df.copy()
                display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')
                st.dataframe(display_df.drop(columns=['ID']), use_container_width=True)
                
                csv = df.drop(columns=['ID']).to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Export Filtered Ledger to CSV", data=csv, file_name=f"{current_user}_spend_ai.csv", mime="text/csv")
                
                st.write("---")
                st.subheader("🗑️ Ledger Purge Console")
                delete_options = {f"ID {row['ID']} | {row['Description']} (₹{row['Amount']})": row['ID'] for _, row in df.iterrows()}
                selected_to_delete = st.selectbox("Select Target Entry to Remove", options=list(delete_options.keys()))
                
                st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
                if st.button("Purge Entry From Database"):
                    target_id = delete_options[selected_to_delete]
                    if delete_expense_inline(target_id, current_user):
                        st.success("Record successfully wiped from storage matrix.")
                        st.rerun()
                    else: st.error("Error executing purge logic.")
                st.markdown('</div>', unsafe_allow_html=True)
                
            with col2:
                st.subheader("Visual Matrix Analytics")
                cat_df = df.groupby('Category')['Amount'].sum().reset_index()
                fig = px.pie(cat_df, values='Amount', names='Category', hole=0.4,
                             color_discrete_sequence=['#22D3EE', '#34D399', '#60A5FA', '#A78BFA', '#F472B6'])
                fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)',
                                  plot_bgcolor='rgba(0,0,0,0)', font_color='#E2E8F0', showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
        else: st.info(f"Welcome Profile Account Agent! No database ledger available for this specific account profile yet.")