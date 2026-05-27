import flet as ft
import sqlite3
from datetime import datetime, timedelta
import re
import csv
from collections import defaultdict
import os
import shutil

PRESET_BANKS = [
    "中国工商银行", "中国建设银行", "中国农业银行", "重庆银行",
    "交通银行", "重庆农村商业银行", "微众银行", "蓝海银行", "三峡银行", "邮储银行", "其他银行",
    "微信理财", "支付宝理财", "股票基金", "银行理财"
]

PRESET_DEPOSIT_TYPES = [
    "活期", "一年期定期", "三年期定期", "五年期定期", "自定义期限定期",
    "大额存单", "结构性存款", "通知存款", "理财产品", "股票基金"
]

class DepositManager:
    def __init__(self, filename="deposits.db"):
        self.filename = filename
        self.conn = sqlite3.connect(filename)
        self._create_tables()
        self.users = self.load_users()
        self.current_user = self.users[0] if self.users else "默认用户"

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deposits'")
        table_exists = cursor.fetchone()
        if table_exists:
            cursor.execute("PRAGMA table_info(deposits)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'is_unlocked' not in columns:
                cursor.execute("ALTER TABLE deposits ADD COLUMN is_unlocked INTEGER DEFAULT 0")
        else:
            cursor.execute("""
            CREATE TABLE deposits (
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
        self.conn.commit()

    def load_users(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_name FROM users ORDER BY id")
        rows = cursor.fetchall()
        return [row[0] for row in rows] if rows else []

    def save_users(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM users")
        for user in self.users:
            cursor.execute("INSERT INTO users (user_name) VALUES (?)", (user,))
        self.conn.commit()

    def add_user(self, user):
        if user and user not in self.users:
            self.users.append(user)
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO users (user_name) VALUES (?)", (user,))
            self.conn.commit()
            return True, f"用户 '{user}' 添加成功"
        return False, "用户已存在或名称无效"

    def delete_user(self, user):
        if user not in self.users:
            return False, f"用户 '{user}' 不存在"
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM deposits WHERE user_name=?", (user,))
        deposit_count = cursor.fetchone()[0]
        if deposit_count > 0:
            return False, f"无法删除用户 '{user}'，该用户仍有{deposit_count}笔存款"
        try:
            cursor.execute("DELETE FROM users WHERE user_name=?", (user,))
            self.conn.commit()
            if user in self.users:
                self.users.remove(user)
            if self.current_user == user:
                self.current_user = self.users[0] if self.users else None
            return True, f"用户 '{user}' 删除成功"
        except Exception as e:
            return False, f"删除用户失败: {str(e)}"

    def rename_user(self, old_name, new_name):
        if not new_name:
            return False, "新用户名不能为空"
        if new_name == old_name:
            return False, "新用户名与旧用户名相同"
        if new_name in self.users:
            return False, f"用户名 '{new_name}' 已存在"
        cursor = self.conn.cursor()
        try:
            cursor.execute("UPDATE users SET user_name=? WHERE user_name=?", (new_name, old_name))
            cursor.execute("UPDATE deposits SET user_name=? WHERE user_name=?", (new_name, old_name))
            self.conn.commit()
            if old_name in self.users:
                index = self.users.index(old_name)
                self.users[index] = new_name
            if self.current_user == old_name:
                self.current_user = new_name
            return True, f"用户 '{old_name}' 已重命名为 '{new_name}'"
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"重命名用户失败: {str(e)}"

    def load_deposits(self):
        cursor = self.conn.cursor()
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
        if deposit.get('start_date') and not self.is_valid_date(deposit['start_date']):
            return False, "起始日期格式无效，请使用 YYYY-MM-DD 格式"
        if deposit.get('maturity_date') and not self.is_valid_date(deposit['maturity_date']):
            return False, "到期日期格式无效，请使用 YYYY-MM-DD 格式"
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
        if deposit['user'] not in self.users:
            self.users.append(deposit['user'])
            self.save_users()
        return True, "存款添加成功"

    def update_deposit(self, deposit_id, deposit):
        if deposit.get('start_date') and not self.is_valid_date(deposit['start_date']):
            return False, "起始日期格式无效，请使用 YYYY-MM-DD 格式"
        if deposit.get('maturity_date') and not self.is_valid_date(deposit['maturity_date']):
            return False, "到期日期格式无效，请使用 YYYY-MM-DD 格式"
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
        if deposit['user'] not in self.users:
            self.users.append(deposit['user'])
            self.save_users()
        return True, "存款更新成功"

    def delete_deposit(self, deposit_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM deposits WHERE id=?", (deposit_id,))
        self.conn.commit()
        return True, "存款删除成功"

    def calculate_interest(self, start_date_str, maturity_date_str, amount, rate, interest_type="simple", as_of_date=None):
        try:
            if not start_date_str or rate is None:
                return 0.0
            start_date_str = self.convert_date_format(start_date_str) or start_date_str
            if maturity_date_str:
                maturity_date_str = self.convert_date_format(maturity_date_str) or maturity_date_str
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            maturity_date = datetime.strptime(maturity_date_str, "%Y-%m-%d") if maturity_date_str else None
            as_of_date = datetime.strptime(as_of_date, "%Y-%m-%d") if isinstance(as_of_date, str) else (as_of_date or datetime.now())
            end_date = min(as_of_date, maturity_date) if maturity_date else as_of_date
            days = (end_date - start_date).days
            if days <= 0:
                return 0.0
            if interest_type == "compound":
                daily_rate = rate / 100 / 365
                interest = amount * ((1 + daily_rate) ** days - 1)
            else:
                daily_rate = rate / 100 / 365
                interest = daily_rate * amount * days
            if maturity_date:
                total_days = (maturity_date - start_date).days
                if interest_type == "compound":
                    total_years = total_days / 365
                    total_interest = amount * (1 + rate / 100) ** total_years - amount
                else:
                    total_interest = daily_rate * amount * total_days
                interest = min(interest, total_interest)
            return round(interest, 2)
        except Exception as e:
            print(f"[利息计算错误] {str(e)}")
            return 0.0

    def calculate_total_interest(self, start_date_str, maturity_date_str, amount, rate, interest_type="simple"):
        return self.calculate_interest(
            start_date_str, maturity_date_str, amount, rate, interest_type, maturity_date_str
        ) if maturity_date_str else self.calculate_interest(
            start_date_str, None, amount, rate, interest_type, datetime.now().strftime("%Y-%m-%d")
        )

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
        total_maturity_interest = 0.0
        if user:
            cursor.execute("SELECT id, deposit_date, maturity_date, amount, interest_rate, interest_type FROM deposits WHERE user_name=?", (user,))
        else:
            cursor.execute("SELECT id, deposit_date, maturity_date, amount, interest_rate, interest_type FROM deposits")
        for row in cursor.fetchall():
            dep_id, start_date, maturity_date, amount, rate, interest_type = row
            try:
                if start_date and rate is not None:
                    current_int = self.calculate_interest(start_date, maturity_date, amount, rate, interest_type)
                    total_current_interest += current_int
                    if maturity_date:
                        mat_int = self.calculate_total_interest(start_date, maturity_date, amount, rate, interest_type)
                    else:
                        mat_int = 0.0
                    total_maturity_interest += mat_int
            except Exception as e:
                print(f"计算存款 {dep_id} 利息时出错: {e}")
                continue
        return {
            'total_amount': total_amount,
            'total_current_interest': total_current_interest,
            'total_maturity_interest': total_maturity_interest,
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

    def restore_from_path(self, source_path):
        """从任意路径恢复数据库"""
        if not os.path.exists(source_path):
            return False, f"文件不存在: {source_path}"
        try:
            self.conn.close()
            shutil.copy2(source_path, self.filename)
            self.conn = sqlite3.connect(self.filename)
            self.users = self.load_users()
            self.current_user = self.users[0] if self.users else "默认用户"
            return True, "恢复成功！请重启应用或刷新页面"
        except Exception as e:
            return False, f"恢复失败: {str(e)}"

    def restore_from_download(self):
        download_path = "/storage/emulated/0/Download/deposits.db"
        return self.restore_from_path(download_path)

    @staticmethod
    def convert_date_format(date_str):
        if not date_str or date_str.strip() == "":
            return None
        if re.match(r'^\d{8}$', date_str.strip()):
            try:
                return datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
            except:
                pass
        formats = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
            "%Y年%m月%d日", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y"
        ]
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str.strip(), fmt)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def is_valid_date(date_str):
        if not date_str:
            return True
        formats = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
            "%Y年%m月%d日", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y%m%d"
        ]
        for fmt in formats:
            try:
                datetime.strptime(date_str, fmt)
                return True
            except ValueError:
                continue
        return False


def main(page: ft.Page):
    page.title = "家庭存款管理系统"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 10
    page.scroll = ft.ScrollMode.AUTO
    page.window_width = 400
    page.window_height = 700

    manager = DepositManager()

    current_user = manager.current_user if manager.current_user else "所有用户"
    deposits = manager.load_deposits()

    deposit_list = ft.ListView(expand=True, spacing=10, padding=10)
    stats_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
    user_selector = ft.Dropdown(
        label="当前用户",
        options=[ft.dropdown.Option("所有用户")] + [ft.dropdown.Option(u) for u in manager.users],
        value=current_user,
        width=200,
    )

    def refresh_data():
        nonlocal deposits
        deposits = manager.load_deposits()
        if current_user != "所有用户":
            filtered = [d for d in deposits if d['user'] == current_user]
        else:
            filtered = deposits
        display_deposits(filtered)
        update_stats()

    def display_deposits(dep_list):
        deposit_list.controls.clear()
        if not dep_list:
            deposit_list.controls.append(ft.Text("暂无存款记录", size=16, color="grey"))
            page.update()
            return
        for dep in dep_list:
            current_interest = 0.0
            if dep['start_date'] and dep['interest_rate'] is not None:
                current_interest = manager.calculate_interest(
                    dep['start_date'], dep['maturity_date'], dep['amount'],
                    dep['interest_rate'], dep['interest_type']
                )
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon("account_balance", size=20, color="blue"),
                            ft.Text(dep['bank'], weight=ft.FontWeight.BOLD, size=16),
                            ft.Container(expand=True),
                            ft.Text(f"{dep['amount']:,.2f}元", size=16, color="green"),
                        ]),
                        ft.Row([
                            ft.Icon("category", size=16, color="grey"),
                            ft.Text(dep['deposit_type'], size=14),
                            ft.Container(width=20),
                            ft.Icon("calendar_today", size=16, color="grey"),
                            ft.Text(f"存入: {dep['start_date'] or '无'}", size=12),
                            ft.Container(width=20),
                            ft.Icon("event", size=16, color="grey"),
                            ft.Text(f"到期: {dep['maturity_date'] or '长期'}", size=12),
                        ]),
                        ft.Row([
                            ft.Text(f"利率: {dep['interest_rate']}%", size=12),
                            ft.Container(width=20),
                            ft.Text(f"计息: {'复利' if dep['interest_type']=='compound' else '单利'}", size=12),
                            ft.Container(width=20),
                            ft.Text(f"当前利息: {current_interest:,.2f}", size=12, color="orange"),
                        ]),
                        ft.Row([
                            ft.IconButton(icon="edit", icon_size=18, on_click=lambda e, d=dep: edit_deposit(d)),
                            ft.IconButton(icon="delete", icon_size=18, on_click=lambda e, d=dep: delete_deposit(d)),
                        ], alignment=ft.MainAxisAlignment.END),
                    ]),
                    padding=10,
                ),
                elevation=2,
            )
            deposit_list.controls.append(card)
        page.update()

    def update_stats():
        stats = manager.get_deposit_stats(None if current_user == "所有用户" else current_user)
        stats_text.value = f"总本金: {stats['total_amount']:,.2f}元   当前利息: {stats['total_current_interest']:,.2f}元"
        page.update()

    def edit_deposit(dep):
        user_dd = ft.Dropdown(label="持有人", options=[ft.dropdown.Option(u) for u in manager.users], value=dep['user'])
        bank_input = ft.TextField(label="银行", value=dep['bank'])
        type_input = ft.TextField(label="存款类型", value=dep['deposit_type'])
        amount_input = ft.TextField(label="金额", value=str(dep['amount']), keyboard_type=ft.KeyboardType.NUMBER)
        start_date = ft.TextField(label="起始日期 (YYYY-MM-DD)", value=dep['start_date'] or "")
        maturity_date = ft.TextField(label="到期日期 (YYYY-MM-DD)", value=dep['maturity_date'] or "")
        rate_input = ft.TextField(label="利率 (%)", value=str(dep['interest_rate']) if dep['interest_rate'] else "")
        interest_type_dd = ft.Dropdown(label="计息类型", options=[ft.dropdown.Option("simple", "单利"), ft.dropdown.Option("compound", "复利")], value=dep['interest_type'])
        notes_input = ft.TextField(label="备注", value=dep['notes'] or "")

        def save_edit(e):
            try:
                new_dep = {
                    'user': user_dd.value,
                    'bank': bank_input.value,
                    'deposit_type': type_input.value,
                    'amount': float(amount_input.value),
                    'start_date': start_date.value if start_date.value else None,
                    'maturity_date': maturity_date.value if maturity_date.value else None,
                    'interest_rate': float(rate_input.value) if rate_input.value else None,
                    'interest_type': interest_type_dd.value,
                    'notes': notes_input.value,
                    'is_unlocked': dep.get('is_unlocked', 0)
                }
                manager.update_deposit(dep['id'], new_dep)
                refresh_data()
                page.close(dlg)
            except Exception as ex:
                page.show_snack_bar(ft.SnackBar(content=ft.Text(f"保存失败: {ex}")))

        dlg = ft.AlertDialog(
            title=ft.Text("编辑存款"),
            content=ft.Container(
                content=ft.Column([user_dd, bank_input, type_input, amount_input, start_date, maturity_date, rate_input, interest_type_dd, notes_input],
                                  height=400, scroll=ft.ScrollMode.AUTO),
                width=350,
            ),
            actions=[ft.TextButton("取消", on_click=lambda e: page.close(dlg)),
                     ft.TextButton("保存", on_click=save_edit)],
        )
        page.open(dlg)

    def delete_deposit(dep):
        def confirm_delete(e):
            manager.delete_deposit(dep['id'])
            refresh_data()
            page.close(confirm_dlg)
        confirm_dlg = ft.AlertDialog(
            title=ft.Text("确认删除"),
            content=ft.Text(f"确定删除 {dep['bank']} - {dep['deposit_type']} 吗？"),
            actions=[ft.TextButton("取消", on_click=lambda e: page.close(confirm_dlg)),
                     ft.TextButton("删除", on_click=confirm_delete)],
        )
        page.open(confirm_dlg)

    def add_deposit_dialog(e):
        user_dd = ft.Dropdown(label="持有人", options=[ft.dropdown.Option(u) for u in manager.users], value=manager.current_user if manager.current_user else "默认用户")
        bank_input = ft.TextField(label="银行", hint_text="银行名称")
        type_input = ft.TextField(label="存款类型", hint_text="定期/活期等")
        amount_input = ft.TextField(label="金额", keyboard_type=ft.KeyboardType.NUMBER)
        start_date = ft.TextField(label="起始日期 (YYYY-MM-DD)", hint_text="2025-01-01")
        maturity_date = ft.TextField(label="到期日期 (YYYY-MM-DD)", hint_text="2026-01-01")
        rate_input = ft.TextField(label="利率 (%)")
        interest_type_dd = ft.Dropdown(label="计息类型", options=[ft.dropdown.Option("simple", "单利"), ft.dropdown.Option("compound", "复利")], value="simple")
        notes_input = ft.TextField(label="备注")

        def save_add(e):
            try:
                new_dep = {
                    'user': user_dd.value,
                    'bank': bank_input.value,
                    'deposit_type': type_input.value,
                    'amount': float(amount_input.value),
                    'start_date': start_date.value if start_date.value else None,
                    'maturity_date': maturity_date.value if maturity_date.value else None,
                    'interest_rate': float(rate_input.value) if rate_input.value else None,
                    'interest_type': interest_type_dd.value,
                    'notes': notes_input.value,
                    'is_unlocked': 0
                }
                manager.add_deposit(new_dep)
                refresh_data()
                page.close(dlg)
            except Exception as ex:
                page.show_snack_bar(ft.SnackBar(content=ft.Text(f"添加失败: {ex}")))

        dlg = ft.AlertDialog(
            title=ft.Text("添加存款"),
            content=ft.Container(
                content=ft.Column([user_dd, bank_input, type_input, amount_input, start_date, maturity_date, rate_input, interest_type_dd, notes_input],
                                  height=400, scroll=ft.ScrollMode.AUTO),
                width=350,
            ),
            actions=[ft.TextButton("取消", on_click=lambda e: page.close(dlg)),
                     ft.TextButton("保存", on_click=save_add)],
        )
        page.open(dlg)

    def show_charts(e):
        page.show_snack_bar(ft.SnackBar(content=ft.Text("图表功能暂不可用，将在后续版本添加")))

    def manage_users(e):
        def refresh_user_list():
            users = manager.users
            user_list.controls.clear()
            for u in users:
                row = ft.Row([
                    ft.Text(u, expand=True),
                    ft.IconButton(icon="edit", on_click=lambda _, name=u: rename_user(name)),
                    ft.IconButton(icon="delete", on_click=lambda _, name=u: delete_user(name)),
                ])
                user_list.controls.append(row)
            page.update()

        def add_user_click(e):
            name = new_user_input.value.strip()
            if name:
                success, msg = manager.add_user(name)
                if success:
                    refresh_user_list()
                    refresh_user_dropdown()
                    page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
                    new_user_input.value = ""
                else:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
            else:
                page.show_snack_bar(ft.SnackBar(content=ft.Text("用户名不能为空")))

        def rename_user(old_name):
            def do_rename(e):
                new_name = rename_input.value.strip()
                if new_name:
                    success, msg = manager.rename_user(old_name, new_name)
                    if success:
                        refresh_user_list()
                        refresh_user_dropdown()
                        page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
                        page.close(rename_dlg)
                    else:
                        page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
                else:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text("新用户名不能为空")))
            rename_input = ft.TextField(label="新用户名", value=old_name)
            rename_dlg = ft.AlertDialog(
                title=ft.Text("重命名用户"),
                content=rename_input,
                actions=[ft.TextButton("取消", on_click=lambda e: page.close(rename_dlg)),
                         ft.TextButton("确定", on_click=do_rename)],
            )
            page.open(rename_dlg)

        def delete_user(user):
            def confirm(e):
                nonlocal current_user
                success, msg = manager.delete_user(user)
                if success:
                    refresh_user_list()
                    refresh_user_dropdown()
                    page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
                    if current_user == user or (current_user == "所有用户" and user == manager.current_user):
                        current_user = "所有用户"
                        user_selector.value = current_user
                        refresh_data()
                    page.close(confirm_dlg)
                else:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
            confirm_dlg = ft.AlertDialog(
                title=ft.Text("确认删除"),
                content=ft.Text(f"确定删除用户 '{user}' 吗？"),
                actions=[ft.TextButton("取消", on_click=lambda e: page.close(confirm_dlg)),
                         ft.TextButton("删除", on_click=confirm)],
            )
            page.open(confirm_dlg)

        user_list = ft.Column(spacing=10)
        new_user_input = ft.TextField(label="新用户名", width=200)
        add_user_btn = ft.ElevatedButton("添加用户", on_click=add_user_click)
        refresh_user_list()

        dlg = ft.AlertDialog(
            title=ft.Text("用户管理"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("现有用户：", weight=ft.FontWeight.BOLD),
                    user_list,
                    ft.Divider(),
                    ft.Row([new_user_input, add_user_btn]),
                ], height=400, scroll=ft.ScrollMode.AUTO),
                width=350,
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: page.close(dlg))],
        )
        page.open(dlg)

    def refresh_user_dropdown():
        user_selector.options = [ft.dropdown.Option("所有用户")] + [ft.dropdown.Option(u) for u in manager.users]
        if current_user in manager.users or current_user == "所有用户":
            user_selector.value = current_user
        else:
            user_selector.value = "所有用户"
        page.update()

    def check_maturities(e):
        upcoming = manager.get_upcoming_maturities()
        if upcoming:
            msg = "未来7天内到期的存款:\n\n"
            for dep in upcoming:
                days_left = (datetime.strptime(dep[5], "%Y-%m-%d") - datetime.now()).days
                msg += f"用户: {dep[1]}\n银行: {dep[2]}\n名称: {dep[3]}\n金额: {dep[4]:.2f}\n到期日: {dep[5]}\n剩余天数: {days_left}\n\n"
            page.show_dialog(ft.AlertDialog(title=ft.Text("到期提醒"), content=ft.Text(msg), actions=[ft.TextButton("确定", on_click=lambda e: page.close(dlg))]))
        else:
            page.show_snack_bar(ft.SnackBar(content=ft.Text("未来7天内没有即将到期的存款")))

    def restore_from_download(e):
        success, msg = manager.restore_from_download()
        if success:
            page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
            refresh_data()
        else:
            page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))

    def restore_manual(e):
        def do_restore(path):
            if not path:
                return
            success, msg = manager.restore_from_path(path.strip())
            if success:
                page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
                refresh_data()
            else:
                page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
            page.close(dlg)

        def on_submit(e):
            do_restore(path_input.value)

        path_input = ft.TextField(label="文件路径", hint_text="例如 /storage/emulated/0/Download/deposits.db", width=400)
        dlg = ft.AlertDialog(
            title=ft.Text("输入数据库文件完整路径"),
            content=ft.Container(content=path_input, padding=10),
            actions=[
                ft.TextButton("取消", on_click=lambda e: page.close(dlg)),
                ft.TextButton("恢复", on_click=on_submit),
            ],
        )
        page.open(dlg)

    def on_user_change(e):
        nonlocal current_user
        current_user = user_selector.value
        refresh_data()

    user_selector.on_change = on_user_change

    top_bar = ft.Row([
        user_selector,
        ft.IconButton(icon="add", icon_size=30, on_click=add_deposit_dialog, tooltip="添加存款"),
        ft.IconButton(icon="pie_chart", icon_size=30, on_click=show_charts, tooltip="统计图表"),
        ft.PopupMenuButton(
            icon="more_vert",
            items=[
                ft.PopupMenuItem(text="用户管理", on_click=manage_users),
                ft.PopupMenuItem(text="到期提醒", on_click=check_maturities),
                ft.PopupMenuItem(text="从 Download 恢复", on_click=restore_from_download),
                ft.PopupMenuItem(text="手动输入路径恢复", on_click=restore_manual),
            ]
        ),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    page.add(
        top_bar,
        stats_text,
        ft.Divider(height=1),
        deposit_list,
    )

    refresh_data()

if __name__ == "__main__":
    ft.app(target=main)
