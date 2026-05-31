"""
存款管理系统 - Kivy 移动端版本
将原始 Tkinter 应用迁移到 Kivy 框架，可打包为 Android APK
"""

import sqlite3
import re
import csv
import chardet
from datetime import datetime, timedelta
from collections import defaultdict
import os
import shutil

# Kivy 相关导入
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.gridlayout import GridLayout
from kivy.uix.recycleview import RecycleView
from kivy.properties import StringProperty, NumericProperty, ListProperty, ObjectProperty
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.clock import Clock

# 图表支持 (Kivy 中使用 matplotlib)
try:
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端，移动端必须
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from kivy.uix.image import Image
    import numpy as np
    from matplotlib.patches import Patch
    from matplotlib.dates import DateFormatter
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("警告: matplotlib 未安装，图表功能不可用")

# 金融计算核心类 - 从原始代码迁移，业务逻辑完全复用
class DepositManager:
    def __init__(self, filename="deposits.db"):
        self.filename = filename
        self.conn = sqlite3.connect(filename)
        self._create_tables()
        self.users = self.load_users()
        self.current_user = self.users[0] if self.users else "默认用户"

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL DEFAULT '其他',
            bank_name TEXT NOT NULL,
            deposit_name TEXT NOT NULL,
            amount REAL NOT NULL,
            deposit_date TEXT,
            maturity_date TEXT,
            interest_rate REAL,
            interest_type TEXT NOT NULL DEFAULT 'simple',
            notes TEXT,
            is_notified INTEGER DEFAULT 0,
            is_unlocked INTEGER DEFAULT 0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT UNIQUE NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deposit_id INTEGER NOT NULL,
            effective_date TEXT NOT NULL,
            interest_rate REAL NOT NULL,
            FOREIGN KEY(deposit_id) REFERENCES deposits(id) ON DELETE CASCADE
        )
        """)
        # 兼容原数据库：如果已有存款表但缺少字段，进行升级
        cursor.execute("PRAGMA table_info(deposits)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_unlocked' not in columns:
            cursor.execute("ALTER TABLE deposits ADD COLUMN is_unlocked INTEGER DEFAULT 0")
        self.conn.commit()
        # 清理可能遗留的无效用户
        cursor.execute("DELETE FROM users WHERE user_name IS NULL OR user_name = ''")
        self.conn.commit()

    def load_users(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_name FROM users ORDER BY id")
        rows = cursor.fetchall()
        if not rows:
            return []
        return [row[0] for row in rows]

    def add_user(self, user_name):
        if not user_name or user_name in self.load_users():
            return False, "用户已存在或名称无效"
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO users (user_name) VALUES (?)", (user_name,))
        self.conn.commit()
        return True, f"用户 {user_name} 添加成功"

    def load_deposits(self, user_name=None):
        cursor = self.conn.cursor()
        if user_name:
            cursor.execute("""
            SELECT id, user_name, bank_name, deposit_name, amount, 
                   deposit_date, maturity_date, interest_rate, interest_type, notes, is_unlocked
            FROM deposits WHERE user_name=?
            """, (user_name,))
        else:
            cursor.execute("""
            SELECT id, user_name, bank_name, deposit_name, amount, 
                   deposit_date, maturity_date, interest_rate, interest_type, notes, is_unlocked
            FROM deposits
            """)
        deposits = []
        for row in cursor.fetchall():
            deposits.append({
                'id': row[0], 'user': row[1] or "其他", 'bank': row[2] or "其他银行",
                'deposit_type': row[3] or "其他类型", 'amount': row[4] or 0.0,
                'start_date': row[5], 'maturity_date': row[6],
                'interest_rate': row[7] if row[7] is not None else 0.0,
                'interest_type': row[8] or "simple", 'notes': row[9] or "",
                'is_unlocked': row[10] or 0
            })
        return deposits

    def add_deposit(self, deposit):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO deposits (user_name, bank_name, deposit_name, amount, 
                            deposit_date, maturity_date, interest_rate, interest_type, notes, is_unlocked)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            deposit['user'], deposit['bank'], deposit['deposit_type'], deposit['amount'],
            deposit.get('start_date', None), deposit.get('maturity_date', None),
            deposit.get('interest_rate', None), deposit.get('interest_type', 'simple'),
            deposit.get('notes', ''), deposit.get('is_unlocked', 0)
        ))
        self.conn.commit()
        new_id = cursor.lastrowid
        if deposit.get('start_date') and deposit.get('interest_rate') is not None:
            cursor.execute("INSERT INTO rate_history (deposit_id, effective_date, interest_rate) VALUES (?,?,?)",
                           (new_id, deposit['start_date'], deposit['interest_rate']))
            self.conn.commit()
        if deposit['user'] not in self.load_users():
            self.add_user(deposit['user'])
        return True, "存款添加成功"

    def update_deposit(self, deposit_id, deposit):
        cursor = self.conn.cursor()
        cursor.execute("""
        UPDATE deposits 
        SET user_name=?, bank_name=?, deposit_name=?, amount=?, 
            deposit_date=?, maturity_date=?, interest_rate=?, interest_type=?, notes=?, is_unlocked=?
        WHERE id=?
        """, (
            deposit['user'], deposit['bank'], deposit['deposit_type'], deposit['amount'],
            deposit.get('start_date', None), deposit.get('maturity_date', None),
            deposit.get('interest_rate', None), deposit.get('interest_type', 'simple'),
            deposit.get('notes', ''), deposit.get('is_unlocked', 0),
            deposit_id
        ))
        self.conn.commit()
        if deposit.get('start_date') and deposit.get('interest_rate') is not None:
            cursor.execute("SELECT id FROM rate_history WHERE deposit_id=? ORDER BY effective_date LIMIT 1", (deposit_id,))
            first = cursor.fetchone()
            if first:
                cursor.execute("UPDATE rate_history SET interest_rate=? WHERE id=?", (deposit['interest_rate'], first[0]))
            else:
                cursor.execute("INSERT INTO rate_history (deposit_id, effective_date, interest_rate) VALUES (?,?,?)",
                               (deposit_id, deposit['start_date'], deposit['interest_rate']))
            self.conn.commit()
        return True, "存款更新成功"

    def delete_deposit(self, deposit_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM deposits WHERE id=?", (deposit_id,))
        self.conn.commit()
        return True, "存款删除成功"

    def get_rate_history(self, deposit_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, effective_date, interest_rate FROM rate_history WHERE deposit_id=? ORDER BY effective_date", (deposit_id,))
        return cursor.fetchall()

    def add_rate_change(self, deposit_id, effective_date, interest_rate):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM rate_history WHERE deposit_id=? AND effective_date=?", (deposit_id, effective_date))
        if cursor.fetchone():
            return False, "该日期已存在利率记录"
        cursor.execute("INSERT INTO rate_history (deposit_id, effective_date, interest_rate) VALUES (?,?,?)",
                       (deposit_id, effective_date, interest_rate))
        self.conn.commit()
        return True, "利率历史已添加"

    def delete_rate_change(self, rate_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM rate_history WHERE id=?", (rate_id,))
        self.conn.commit()
        return True, "已删除"

    def calculate_interest(self, start_date_str, maturity_date_str, amount, rate, interest_type="simple",
                           as_of_date=None, deposit_id=None):
        try:
            if not start_date_str or amount <= 0:
                return 0.0
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            maturity_date = None
            if maturity_date_str:
                maturity_date = datetime.strptime(maturity_date_str, "%Y-%m-%d")
            as_of_date = datetime.strptime(as_of_date, "%Y-%m-%d") if isinstance(as_of_date, str) else (as_of_date or datetime.now())
            end_date = min(as_of_date, maturity_date) if maturity_date else as_of_date
            if end_date <= start_date:
                return 0.0
            if deposit_id:
                hist = self.get_rate_history(deposit_id)
                if hist:
                    periods = []
                    prev_date = start_date
                    for rid, eff_date, r in hist:
                        eff = datetime.strptime(eff_date, "%Y-%m-%d")
                        if eff > start_date:
                            if prev_date < eff:
                                periods.append((prev_date, min(eff, end_date), r))
                            prev_date = eff
                    if prev_date < end_date:
                        last_rate = hist[-1][2] if hist else rate
                        periods.append((prev_date, end_date, last_rate))
                else:
                    periods = [(start_date, end_date, rate)]
            else:
                periods = [(start_date, end_date, rate)]
            total_interest = 0.0
            for p_start, p_end, r in periods:
                if p_end <= p_start:
                    continue
                days = (p_end - p_start).days
                if interest_type == "compound":
                    daily_rate = r / 100 / 365
                    interest = amount * ((1 + daily_rate) ** days - 1)
                else:
                    daily_rate = r / 100 / 365
                    interest = daily_rate * amount * days
                total_interest += interest
            return round(total_interest, 2)
        except Exception as e:
            print(f"[分段利息计算错误] {str(e)}")
            return 0.0

    def get_deposit_stats(self, user=None):
        cursor = self.conn.cursor()
        if user:
            cursor.execute("SELECT SUM(amount) FROM deposits WHERE user_name=?", (user,))
        else:
            cursor.execute("SELECT SUM(amount) FROM deposits")
        total_amount = cursor.fetchone()[0] or 0.0
        if user:
            cursor.execute("SELECT user_name, SUM(amount) FROM deposits WHERE user_name=? GROUP BY user_name", (user,))
        else:
            cursor.execute("SELECT user_name, SUM(amount) FROM deposits GROUP BY user_name")
        by_holder = {row[0]: row[1] for row in cursor.fetchall()}
        if user:
            cursor.execute("SELECT deposit_name, SUM(amount) FROM deposits WHERE user_name=? GROUP BY deposit_name", (user,))
        else:
            cursor.execute("SELECT deposit_name, SUM(amount) FROM deposits GROUP BY deposit_name")
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        if user:
            cursor.execute("SELECT bank_name, SUM(amount) FROM deposits WHERE user_name=? GROUP BY bank_name", (user,))
        else:
            cursor.execute("SELECT bank_name, SUM(amount) FROM deposits GROUP BY bank_name")
        by_bank = {row[0]: row[1] for row in cursor.fetchall()}
        total_current_interest = 0.0
        if user:
            cursor.execute("SELECT id, deposit_date, maturity_date, amount, interest_rate, interest_type FROM deposits WHERE user_name=?", (user,))
        else:
            cursor.execute("SELECT id, deposit_date, maturity_date, amount, interest_rate, interest_type FROM deposits")
        for row in cursor.fetchall():
            dep_id, start_date, maturity_date, amount, rate, interest_type = row
            if start_date and rate is not None:
                current_int = self.calculate_interest(start_date, maturity_date, amount, rate, interest_type, deposit_id=dep_id)
                total_current_interest += current_int
        return {
            'total_amount': total_amount,
            'total_current_interest': total_current_interest,
            'by_holder': by_holder,
            'by_type': by_type,
            'by_bank': by_bank
        }

    def get_upcoming_maturities(self, days_ahead=7):
        today = datetime.now().strftime("%Y-%m-%d")
        target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT id, user_name, bank_name, deposit_name, amount, maturity_date 
        FROM deposits 
        WHERE maturity_date BETWEEN ? AND ? AND is_notified = 0
        ORDER BY maturity_date
        """, (today, target_date))
        return cursor.fetchall()

    def close(self):
        if self.conn:
            self.conn.close()

    @staticmethod
    def is_valid_date(date_str):
        if not date_str:
            return True
        formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"]
        for fmt in formats:
            try:
                datetime.strptime(date_str, fmt)
                return True
            except ValueError:
                continue
        return False

    @staticmethod
    def convert_date_format(date_str):
        if not date_str or date_str.strip() == "":
            return None
        if re.match(r'^\d{8}$', date_str.strip()):
            try:
                return datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
            except:
                pass
        formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"]
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str.strip(), fmt)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None


# Kivy 界面定义 (KV 语言 - 简化版，实际使用 .kv 文件)
KV_CODE = '''
<DepositItem@BoxLayout>:
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(50)
    Label:
        text: root.bank
        size_hint_x: 0.15
    Label:
        text: root.deposit_type
        size_hint_x: 0.15
    Label:
        text: root.holder
        size_hint_x: 0.1
    Label:
        text: root.amount
        size_hint_x: 0.15
    Label:
        text: root.maturity_date
        size_hint_x: 0.15
    Label:
        text: root.current_interest
        size_hint_x: 0.15

<DepositListView@ScrollView>:
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: self.minimum_height
        id: deposit_container

<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(5)
        
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(5)
            Label:
                text: '存款管理系统'
                font_size: '20sp'
                bold: True
            Button:
                text: '添加'
                size_hint_x: None
                width: dp(60)
                on_release: root.show_add_dialog()
            Button:
                text: '统计'
                size_hint_x: None
                width: dp(60)
                on_release: root.show_stats()
            Button:
                text: '到期提醒'
                size_hint_x: None
                width: dp(80)
                on_release: root.check_maturities()
        
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(5)
            Spinner:
                id: user_spinner
                text: root.current_user_text
                values: root.user_list
                size_hint_x: 0.3
                on_text: root.change_user(self.text)
            TextInput:
                id: search_input
                hint_text: '搜索银行/类型/持有人'
                size_hint_x: 0.7
                on_text: root.search_filter(self.text)
        
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            Label:
                text: '银行'
                bold: True
                size_hint_x: 0.15
            Label:
                text: '类型'
                bold: True
                size_hint_x: 0.15
            Label:
                text: '持有人'
                bold: True
                size_hint_x: 0.1
            Label:
                text: '金额(元)'
                bold: True
                size_hint_x: 0.15
            Label:
                text: '到期日期'
                bold: True
                size_hint_x: 0.15
            Label:
                text: '当前利息'
                bold: True
                size_hint_x: 0.15
        
        DepositListView:
            id: deposit_list
        
        Label:
            id: status_label
            text: ''
            size_hint_y: None
            height: dp(30)
'''


class DepositItem(BoxLayout):
    bank = StringProperty('')
    deposit_type = StringProperty('')
    holder = StringProperty('')
    amount = StringProperty('')
    maturity_date = StringProperty('')
    current_interest = StringProperty('')
    deposit_id = NumericProperty(0)


class DepositListView(ScrollView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.container = None

    def on_kv_post(self, base_widget):
        self.container = self.ids.deposit_container

    def update_items(self, deposits):
        self.container.clear_widgets()
        for dep in deposits:
            item = DepositItem(
                bank=dep['bank'],
                deposit_type=dep['deposit_type'],
                holder=dep['user'],
                amount=f"{dep['amount']:,.2f}",
                maturity_date=dep['maturity_date'] or '长期',
                current_interest=f"{dep.get('current_interest', 0):,.2f}",
                deposit_id=dep['id']
            )
            self.container.add_widget(item)


class AddDepositPopup(Popup):
    def __init__(self, app, deposit=None, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.deposit = deposit
        self.title = "编辑存款" if deposit else "添加存款"
        self.size_hint = (0.9, 0.85)
        self._build_content()

    def _build_content(self):
        layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        # 持有人
        layout.add_widget(Label(text='存款持有人:', size_hint_y=None, height=dp(30)))
        self.user_input = TextInput(size_hint_y=None, height=dp(40))
        if self.deposit:
            self.user_input.text = self.deposit['user']
        else:
            self.user_input.text = self.app.manager.current_user
        layout.add_widget(self.user_input)
        # 银行
        layout.add_widget(Label(text='银行名称:', size_hint_y=None, height=dp(30)))
        self.bank_input = TextInput(size_hint_y=None, height=dp(40))
        if self.deposit:
            self.bank_input.text = self.deposit['bank']
        layout.add_widget(self.bank_input)
        # 存款类型
        layout.add_widget(Label(text='存款类型:', size_hint_y=None, height=dp(30)))
        self.type_input = TextInput(size_hint_y=None, height=dp(40))
        if self.deposit:
            self.type_input.text = self.deposit['deposit_type']
        layout.add_widget(self.type_input)
        # 金额
        layout.add_widget(Label(text='存款金额(元):', size_hint_y=None, height=dp(30)))
        self.amount_input = TextInput(size_hint_y=None, height=dp(40), input_filter='float')
        if self.deposit:
            self.amount_input.text = str(self.deposit['amount'])
        layout.add_widget(self.amount_input)
        # 起始日期
        layout.add_widget(Label(text='起始日期 (YYYY-MM-DD):', size_hint_y=None, height=dp(30)))
        self.start_date_input = TextInput(size_hint_y=None, height=dp(40))
        if self.deposit and self.deposit.get('start_date'):
            self.start_date_input.text = self.deposit['start_date']
        layout.add_widget(self.start_date_input)
        # 到期日期
        layout.add_widget(Label(text='到期日期 (YYYY-MM-DD):', size_hint_y=None, height=dp(30)))
        self.maturity_date_input = TextInput(size_hint_y=None, height=dp(40))
        if self.deposit and self.deposit.get('maturity_date'):
            self.maturity_date_input.text = self.deposit['maturity_date']
        layout.add_widget(self.maturity_date_input)
        # 利率
        layout.add_widget(Label(text='利率(%):', size_hint_y=None, height=dp(30)))
        self.rate_input = TextInput(size_hint_y=None, height=dp(40), input_filter='float')
        if self.deposit and self.deposit.get('interest_rate'):
            self.rate_input.text = str(self.deposit['interest_rate'])
        layout.add_widget(self.rate_input)
        # 计息类型
        layout.add_widget(Label(text='计息类型:', size_hint_y=None, height=dp(30)))
        self.interest_type_spinner = Spinner(text='simple', values=['simple', 'compound'], size_hint_y=None, height=dp(40))
        if self.deposit:
            self.interest_type_spinner.text = self.deposit['interest_type']
        layout.add_widget(self.interest_type_spinner)
        # 备注
        layout.add_widget(Label(text='备注:', size_hint_y=None, height=dp(30)))
        self.notes_input = TextInput(size_hint_y=None, height=dp(60))
        if self.deposit:
            self.notes_input.text = self.deposit['notes']
        layout.add_widget(self.notes_input)
        # 按钮
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        save_btn = Button(text='保存')
        save_btn.bind(on_release=self.save)
        cancel_btn = Button(text='取消')
        cancel_btn.bind(on_release=self.dismiss)
        btn_layout.add_widget(save_btn)
        btn_layout.add_widget(cancel_btn)
        layout.add_widget(btn_layout)
        self.content = layout

    def save(self, instance):
        try:
            amount = float(self.amount_input.text) if self.amount_input.text else 0
            rate = float(self.rate_input.text) if self.rate_input.text else None
        except ValueError:
            self._show_error("金额或利率格式错误")
            return
        if amount <= 0:
            self._show_error("存款金额必须为正数")
            return
        start_date = self.start_date_input.text.strip()
        if start_date and not DepositManager.is_valid_date(start_date):
            self._show_error("起始日期格式无效，请使用 YYYY-MM-DD")
            return
        maturity_date = self.maturity_date_input.text.strip()
        if maturity_date and not DepositManager.is_valid_date(maturity_date):
            self._show_error("到期日期格式无效，请使用 YYYY-MM-DD")
            return
        deposit_data = {
            'user': self.user_input.text.strip(),
            'bank': self.bank_input.text.strip(),
            'deposit_type': self.type_input.text.strip(),
            'amount': amount,
            'start_date': start_date or None,
            'maturity_date': maturity_date or None,
            'interest_rate': rate,
            'interest_type': self.interest_type_spinner.text,
            'notes': self.notes_input.text.strip(),
            'is_unlocked': 0
        }
        if not deposit_data['user'] or not deposit_data['bank'] or not deposit_data['deposit_type']:
            self._show_error("请填写所有必填字段")
            return
        if self.deposit:
            success, msg = self.app.manager.update_deposit(self.deposit['id'], deposit_data)
        else:
            success, msg = self.app.manager.add_deposit(deposit_data)
        if success:
            self.dismiss()
            self.app.refresh_deposits()
        else:
            self._show_error(msg)

    def _show_error(self, msg):
        popup = Popup(title='错误', content=Label(text=msg), size_hint=(0.8, 0.3))
        popup.open()


class StatsPopup(Popup):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.title = "存款统计"
        self.size_hint = (0.95, 0.85)
        self._build_content()

    def _build_content(self):
        stats = self.app.manager.get_deposit_stats(self.app.manager.current_user)
        layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        # 总金额
        total_frame = BoxLayout(size_hint_y=None, height=dp(40))
        total_frame.add_widget(Label(text='总存款金额:', size_hint_x=0.5))
        total_frame.add_widget(Label(text=f"{stats['total_amount']:,.2f} 元", size_hint_x=0.5))
        layout.add_widget(total_frame)
        # 当前利息
        interest_frame = BoxLayout(size_hint_y=None, height=dp(40))
        interest_frame.add_widget(Label(text='当前总利息:', size_hint_x=0.5))
        interest_frame.add_widget(Label(text=f"{stats['total_current_interest']:,.2f} 元", size_hint_x=0.5))
        layout.add_widget(interest_frame)
        # 按持有人
        layout.add_widget(Label(text='按持有人统计:', size_hint_y=None, height=dp(30), bold=True))
        for holder, amount in stats['by_holder'].items():
            line = BoxLayout(size_hint_y=None, height=dp(30))
            line.add_widget(Label(text=holder, size_hint_x=0.5))
            line.add_widget(Label(text=f"{amount:,.2f} 元", size_hint_x=0.5))
            layout.add_widget(line)
        # 按银行
        layout.add_widget(Label(text='按银行统计:', size_hint_y=None, height=dp(30), bold=True))
        for bank, amount in stats['by_bank'].items():
            line = BoxLayout(size_hint_y=None, height=dp(30))
            line.add_widget(Label(text=bank[:15], size_hint_x=0.5))
            line.add_widget(Label(text=f"{amount:,.2f} 元", size_hint_x=0.5))
            layout.add_widget(line)
        scroll = ScrollView()
        scroll.add_widget(layout)
        self.content = scroll

    def on_dismiss(self):
        pass


class MainScreen(Screen):
    current_user_text = StringProperty('')
    user_list = ListProperty([])

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.all_deposits = []
        self.filtered_deposits = []
        self._update_user_list()

    def on_kv_post(self, base_widget):
        self.refresh_deposits()

    def _update_user_list(self):
        users = self.app.manager.load_users()
        self.user_list = users if users else ['默认用户']
        if self.app.manager.current_user:
            self.current_user_text = self.app.manager.current_user
        else:
            self.current_user_text = self.user_list[0] if self.user_list else '默认用户'
        if hasattr(self, 'ids') and 'user_spinner' in self.ids:
            self.ids.user_spinner.values = self.user_list

    def refresh_deposits(self):
        self.all_deposits = self.app.manager.load_deposits(self.app.manager.current_user)
        self._calculate_current_interest()
        self._apply_search()
        self._update_status()

    def _calculate_current_interest(self):
        for dep in self.all_deposits:
            if dep['start_date'] and dep.get('interest_rate') is not None:
                try:
                    current_int = self.app.manager.calculate_interest(
                        dep['start_date'], dep['maturity_date'], dep['amount'],
                        dep['interest_rate'], dep['interest_type'], deposit_id=dep['id']
                    )
                    dep['current_interest'] = current_int
                except:
                    dep['current_interest'] = 0.0
            else:
                dep['current_interest'] = 0.0

    def _apply_search(self):
        search_text = self.ids.search_input.text.strip().lower() if 'search_input' in self.ids else ''
        if search_text:
            self.filtered_deposits = [
                d for d in self.all_deposits
                if search_text in d['bank'].lower()
                or search_text in d['deposit_type'].lower()
                or search_text in d['user'].lower()
                or (d.get('notes') and search_text in d['notes'].lower())
            ]
        else:
            self.filtered_deposits = self.all_deposits.copy()
        self.filtered_deposits.sort(key=lambda x: x.get('maturity_date') or '2099-12-31')
        if 'deposit_list' in self.ids:
            self.ids.deposit_list.update_items(self.filtered_deposits)

    def _update_status(self):
        total_amount = sum(d['amount'] for d in self.filtered_deposits)
        total_interest = sum(d.get('current_interest', 0) for d in self.filtered_deposits)
        status_text = f"共 {len(self.filtered_deposits)} 条记录 | 本金: {total_amount:,.2f} 元 | 当前利息: {total_interest:,.2f} 元"
        if 'status_label' in self.ids:
            self.ids.status_label.text = status_text

    def change_user(self, user):
        self.app.manager.current_user = user
        self.current_user_text = user
        self.refresh_deposits()

    def search_filter(self, text):
        self._apply_search()
        self._update_status()

    def show_add_dialog(self):
        popup = AddDepositPopup(self.app)
        popup.open()

    def show_stats(self):
        popup = StatsPopup(self.app)
        popup.open()

    def check_maturities(self):
        upcoming = self.app.manager.get_upcoming_maturities()
        if upcoming:
            msg = "未来7天内到期的存款:\n\n"
            for dep in upcoming:
                days_left = (datetime.strptime(dep[5], "%Y-%m-%d") - datetime.now()).days
                msg += f"用户: {dep[1]}\n银行: {dep[2]}\n名称: {dep[3]}\n金额: {dep[4]:.2f}\n到期日: {dep[5]}\n剩余天数: {days_left}\n\n"
            popup = Popup(title='到期提醒', content=Label(text=msg), size_hint=(0.9, 0.8))
            popup.open()
        else:
            popup = Popup(title='到期提醒', content=Label(text='未来7天内没有即将到期的存款'), size_hint=(0.7, 0.3))
            popup.open()


class DepositApp(App):
    def build(self):
        Window.clearcolor = (0.95, 0.95, 0.95, 1)
        self.manager = DepositManager()
        self.sm = ScreenManager()
        self.main_screen = MainScreen(self)
        self.sm.add_widget(self.main_screen)
        return self.sm

    def refresh_deposits(self):
        self.main_screen.refresh_deposits()

    def on_stop(self):
        if hasattr(self, 'manager'):
            self.manager.close()


if __name__ == '__main__':
    DepositApp().run()
