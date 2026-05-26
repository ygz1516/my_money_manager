import flet as ft
import sqlite3
from datetime import datetime, timedelta
import re
import csv
import chardet
from collections import defaultdict
import matplotlib.pyplot as plt
import io
import base64
import pandas as pd
import numpy as np
import shutil
import os


# ======================= 原程序的核心业务类（完整保留）=======================
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

    def delete_multiple_deposits(self, deposit_ids):
        if not deposit_ids:
            return False, "没有选择存款记录"
        cursor = self.conn.cursor()
        placeholders = ','.join(['?'] * len(deposit_ids))
        try:
            cursor.execute(f"DELETE FROM deposits WHERE id IN ({placeholders})", deposit_ids)
            self.conn.commit()
            return True, f"成功删除 {len(deposit_ids)} 条存款记录"
        except sqlite3.Error as e:
            return False, f"删除失败: {str(e)}"

    def unlock_deposit(self, deposit_id):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE deposits SET is_unlocked=1 WHERE id=?", (deposit_id,))
        self.conn.commit()
        return True, "存款已解锁"

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

    def export_to_csv(self, filename):
        try:
            deposits = self.load_deposits()
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["序号", "用户", "银行", "存款名称", "金额(元)", "存入日期",
                                 "到期日期", "利率(%)", "计息类型", "备注", "解锁状态"])
                for dep in deposits:
                    amount_str = f"{dep['amount']:,.2f}"
                    unlocked = "是" if dep['is_unlocked'] else "否"
                    writer.writerow([
                        dep['id'], dep['user'], dep['bank'], dep['deposit_type'],
                        amount_str, dep['start_date'], dep['maturity_date'],
                        dep['interest_rate'], dep['interest_type'], dep['notes'], unlocked
                    ])
            return True
        except Exception as e:
            return False

    def export_template(self, filename):
        try:
            headers = ["银行", "存款类型", "持有人", "金额", "起始日期", "到期日期", "利率", "计息类型", "备注"]
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                example_data = [
                    ["中国工商银行", "一年期定期", "张三", 10000.00, "2025-01-01", "2026-01-01", 1.75, "simple", "示例存款"]
                ]
                df = pd.DataFrame(example_data, columns=headers)
                with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='存款模板')
            else:
                with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerow(["中国工商银行", "一年期定期", "张三", "10000.00", "2025-01-01", "2026-01-01", "1.75", "simple", "示例存款"])
            return True
        except Exception as e:
            print(f"导出模板错误: {str(e)}")
            return False

    def import_from_file(self, filename):
        try:
            if filename.lower().endswith(('.xlsx', '.xls')):
                return self.import_from_excel(filename)
            else:
                return self.import_from_csv(filename)
        except Exception as e:
            return False, f"导入文件时出错: {str(e)}"

    def import_from_excel(self, filename):
        try:
            df = pd.read_excel(filename, sheet_name=0)
            has_header = any(col in df.columns for col in ["银行", "bank"])
            if not has_header:
                df.columns = ["银行", "存款类型", "持有人", "金额", "起始日期", "到期日期", "利率", "计息类型", "备注"]
            new_deposits = []
            unknown_users = set()
            def get_date(value):
                if pd.isna(value) or value == "":
                    return ""
                if isinstance(value, pd.Timestamp):
                    return value.strftime("%Y-%m-%d")
                return str(value).strip()
            for _, row in df.iterrows():
                bank = row.get('银行', '') or row.get('bank', '') or "其他银行"
                deposit_type = row.get('存款类型', '') or row.get('deposit_type', '') or "其他类型"
                user = row.get('持有人', '') or row.get('user', '') or "其他"
                amount = row.get('金额', 0) or row.get('amount', 0)
                start_date_raw = row.get('起始日期', '') or row.get('deposit_date', '') or row.get('存入日期', '')
                start_date_raw = get_date(start_date_raw)
                maturity_date_raw = row.get('到期日期', '') or row.get('maturity_date', '')
                maturity_date_raw = get_date(maturity_date_raw)
                rate = row.get('利率', 0) or row.get('interest_rate', 0)
                interest_type = row.get('计息类型', 'simple') or row.get('interest_type', 'simple') or "simple"
                notes = row.get('备注', '') or row.get('notes', '') or ""
                if user not in self.users:
                    unknown_users.add(user)
                start_date = self.convert_date_format(start_date_raw)
                maturity_date = self.convert_date_format(maturity_date_raw)
                if not all([bank, deposit_type, user, amount]):
                    continue
                try:
                    if isinstance(amount, str):
                        amount = float(amount.replace(',', ''))
                except ValueError:
                    continue
                rate_value = None
                if rate and str(rate).strip() != '':
                    try:
                        rate_str = str(rate).replace('%', '').strip()
                        rate_value = float(rate_str)
                    except ValueError:
                        if deposit_type in ["活期", "理财产品", "股票基金"]:
                            rate_value = 0.0
                        else:
                            continue
                else:
                    if deposit_type in ["活期", "理财产品", "股票基金"]:
                        rate_value = 0.0
                    else:
                        continue
                new_deposits.append({
                    'user': user, 'bank': bank, 'deposit_type': deposit_type,
                    'amount': amount, 'start_date': start_date, 'maturity_date': maturity_date,
                    'interest_rate': rate_value, 'interest_type': interest_type, 'notes': notes
                })
            if unknown_users:
                return False, f"导入失败：以下用户不存在，请先添加：\n{', '.join(unknown_users)}"
            cursor = self.conn.cursor()
            for dep in new_deposits:
                cursor.execute("""
                INSERT INTO deposits (user_name, bank_name, deposit_name, amount, deposit_date, maturity_date, interest_rate, interest_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    dep['user'], dep['bank'], dep['deposit_type'], dep['amount'],
                    dep.get('start_date', None), dep.get('maturity_date', None),
                    dep.get('interest_rate', None), dep.get('interest_type', 'simple'), dep.get('notes', '')
                ))
            self.conn.commit()
            return True, f"成功导入 {len(new_deposits)} 条存款记录"
        except Exception as e:
            return False, f"导入Excel文件时出错: {str(e)}"

    def import_from_csv(self, filename):
        try:
            with open(filename, 'rb') as f:
                raw_data = f.read(10000)
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
            with open(filename, 'r', encoding=encoding) as f:
                first_line = f.readline()
                f.seek(0)
                has_header = "银行" in first_line or "bank" in first_line.lower()
                reader = csv.DictReader(f) if has_header else csv.reader(f)
                if not has_header:
                    fieldnames = ["银行", "存款类型", "持有人", "金额", "起始日期", "到期日期", "利率", "计息类型", "备注"]
                    reader = csv.DictReader(f, fieldnames=fieldnames)
                new_deposits = []
                unknown_users = set()
                for row in reader:
                    bank = row.get('银行', row.get('bank', '')) or "其他银行"
                    deposit_type = row.get('存款类型', row.get('deposit_type', row.get('存款名称', ''))) or "其他类型"
                    user = row.get('持有人', row.get('user', row.get('用户', ''))) or "其他"
                    amount = row.get('金额', row.get('amount', '0'))
                    start_date_raw = row.get('起始日期', row.get('deposit_date', row.get('存入日期', '')))
                    maturity_date_raw = row.get('到期日期', row.get('maturity_date', ''))
                    rate = row.get('利率', row.get('interest_rate', '0'))
                    interest_type = row.get('计息类型', row.get('interest_type', 'simple')) or "simple"
                    notes = row.get('备注', row.get('notes', '')) or ""
                    if user not in self.users:
                        unknown_users.add(user)
                    start_date = self.convert_date_format(start_date_raw)
                    maturity_date = self.convert_date_format(maturity_date_raw)
                    if not all([bank, deposit_type, user, amount]):
                        continue
                    try:
                        amount = float(amount.replace(',', '')) if isinstance(amount, str) else float(amount)
                    except ValueError:
                        continue
                    rate_value = 0.0
                    if rate:
                        try:
                            if '%' in rate:
                                rate = rate.replace('%', '').strip()
                            rate_value = float(rate) if rate != '' else 0.0
                        except ValueError:
                            if deposit_type in ["活期", "理财产品", "股票基金"]:
                                rate_value = 0.0
                            else:
                                continue
                    else:
                        if deposit_type in ["活期", "理财产品", "股票基金"]:
                            rate_value = 0.0
                        else:
                            continue
                    new_deposits.append({
                        'user': user, 'bank': bank, 'deposit_type': deposit_type,
                        'amount': amount, 'start_date': start_date, 'maturity_date': maturity_date,
                        'interest_rate': rate_value, 'interest_type': interest_type, 'notes': notes
                    })
                if unknown_users:
                    return False, f"导入失败：以下用户不存在，请先添加：\n{', '.join(unknown_users)}"
                cursor = self.conn.cursor()
                for dep in new_deposits:
                    cursor.execute("""
                    INSERT INTO deposits (user_name, bank_name, deposit_name, amount, deposit_date, maturity_date, interest_rate, interest_type, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        dep['user'], dep['bank'], dep['deposit_type'], dep['amount'],
                        dep.get('start_date', None), dep.get('maturity_date', None),
                        dep.get('interest_rate', None), dep.get('interest_type', 'simple'), dep.get('notes', '')
                    ))
                self.conn.commit()
                return True, f"成功导入 {len(new_deposits)} 条存款记录"
        except Exception as e:
            return False, f"导入存款记录时出错: {str(e)}"

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

# ======================= Flet 手机 APP =======================

def main(page: ft.Page):
    page.title = "家庭存款管理系统"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 10
    page.scroll = ft.ScrollMode.AUTO
    page.window_width = 400
    page.window_height = 700

    manager = DepositManager()

    # 全局状态
    current_user = manager.current_user if manager.current_user else "所有用户"
    deposits = manager.load_deposits()

    # UI 组件引用
    deposit_list = ft.ListView(expand=True, spacing=10, padding=10)
    stats_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
    user_selector = ft.Dropdown(
        label="当前用户",
        options=[ft.dropdown.Option("所有用户")] + [ft.dropdown.Option(u) for u in manager.users],
        value=current_user,
        width=200,
    )

    # ---------- 辅助函数 ----------
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

    # ---------- 编辑 / 删除 ----------
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

    # ---------- 添加存款 ----------
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

    # ---------- 图表统计 ----------
    def show_charts(e):
        stats = manager.get_deposit_stats(None if current_user == "所有用户" else current_user)
        if not stats['by_type'] and not stats['by_bank'] and not stats['by_holder']:
            page.show_snack_bar(ft.SnackBar(content=ft.Text("无数据，无法显示图表")))
            return

        # 移动端字体设置（Android自带字体支持中文）
        plt.rcParams['font.sans-serif'] = ['Droid Sans Fallback', 'Noto Sans CJK SC', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        fig, axes = plt.subplots(1, 3, figsize=(12, 4))
        # 按类型
        labels = list(stats['by_type'].keys())
        sizes = list(stats['by_type'].values())
        if sizes:
            axes[0].pie(sizes, labels=labels, autopct='%1.1f%%')
            axes[0].set_title('存款类型')
        else:
            axes[0].text(0.5, 0.5, '无数据', ha='center', va='center')
        # 按银行
        labels2 = list(stats['by_bank'].keys())
        sizes2 = list(stats['by_bank'].values())
        if sizes2:
            axes[1].pie(sizes2, labels=labels2, autopct='%1.1f%%')
            axes[1].set_title('银行分布')
        else:
            axes[1].text(0.5, 0.5, '无数据', ha='center', va='center')
        # 按持有人
        labels3 = list(stats['by_holder'].keys())
        sizes3 = list(stats['by_holder'].values())
        if sizes3:
            axes[2].pie(sizes3, labels=labels3, autopct='%1.1f%%')
            axes[2].set_title('持有人')
        else:
            axes[2].text(0.5, 0.5, '无数据', ha='center', va='center')

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img_data = base64.b64encode(buf.read()).decode()
        buf.close()
        plt.close()

        img = ft.Image(src_base64=img_data, width=page.width-40, fit=ft.ImageFit.CONTAIN)
        chart_dlg = ft.AlertDialog(
            title=ft.Text("存款图表"),
            content=ft.Container(content=img, width=400, height=400),
            actions=[ft.TextButton("关闭", on_click=lambda e: page.close(chart_dlg))],
        )
        page.open(chart_dlg)

    # ---------- 用户管理 ----------
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
                success, msg = manager.delete_user(user)
                if success:
                    refresh_user_list()
                    refresh_user_dropdown()
                    page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
                    # 修复：删除用户后，如果当前选中的用户被删除了，切换到“所有用户”
                    nonlocal current_user
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

        # 构建用户管理对话框
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

    # ---------- 到期提醒 ----------
    def check_maturities(e):
        upcoming = manager.get_upcoming_maturities()
        if upcoming:
            msg = "未来7天内到期的存款:\n\n"
            for dep in upcoming:
                days_left = (datetime.strptime(dep[5], "%Y-%m-%d") - datetime.now()).days
                msg += f"用户: {dep[1]}\n银行: {dep[2]}\n名称: {dep[3]}\n金额: {dep[4]:.2f}\n到期日: {dep[5]}\n剩余天数: {days_left}\n\n"
            dlg = ft.AlertDialog(title=ft.Text("到期提醒"), content=ft.Text(msg), actions=[ft.TextButton("确定", on_click=lambda e: page.close(dlg))])
            page.open(dlg)
        else:
            page.show_snack_bar(ft.SnackBar(content=ft.Text("未来7天内没有即将到期的存款")))

    # ---------- 导入导出（使用 FilePicker）----------
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    def import_data(e):
        file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["csv", "xlsx"])
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                path = result.files[0].path
                success, msg = manager.import_from_file(path)
                if success:
                    refresh_data()
                    refresh_user_dropdown()
                    page.show_snack_bar(ft.SnackBar(content=ft.Text(msg)))
                else:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text(f"导入失败: {msg}")))
        file_picker.on_result = on_result

    def export_data(e):
        file_picker.save_file(file_name="存款记录.csv", allowed_extensions=["csv"])
        def on_save(result: ft.FilePickerResultEvent):
            if result.path:
                success = manager.export_to_csv(result.path)
                if success:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text("导出成功")))
                else:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text("导出失败")))
        file_picker.on_result = on_save

    def export_template(e):
        file_picker.save_file(file_name="存款导入模板.xlsx", allowed_extensions=["xlsx"])
        def on_save(result: ft.FilePickerResultEvent):
            if result.path:
                success = manager.export_template(result.path)
                if success:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text("模板导出成功")))
                else:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text("模板导出失败")))
        file_picker.on_result = on_save

    # ---------- 备份恢复 ----------
    def backup_db(e):
        if not os.path.exists(manager.filename):
            page.show_snack_bar(ft.SnackBar(content=ft.Text("数据库文件不存在")))
            return
        file_picker.save_file(file_name=f"deposits_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db", allowed_extensions=["db"])
        def on_save(result: ft.FilePickerResultEvent):
            if result.path:
                shutil.copy2(manager.filename, result.path)
                page.show_snack_bar(ft.SnackBar(content=ft.Text("备份成功")))
        file_picker.on_result = on_save

    def restore_db(e):
        file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["db"])
        def on_result(result: ft.FilePickerResultEvent):
            if result.files:
                path = result.files[0].path
                try:
                    manager.conn.close()
                    shutil.copy2(path, manager.filename)
                    manager.conn = sqlite3.connect(manager.filename)
                    manager.users = manager.load_users()
                    manager.current_user = manager.users[0] if manager.users else "默认用户"
                    refresh_data()
                    refresh_user_dropdown()
                    page.show_snack_bar(ft.SnackBar(content=ft.Text("恢复成功")))
                except Exception as ex:
                    page.show_snack_bar(ft.SnackBar(content=ft.Text(f"恢复失败: {ex}")))
        file_picker.on_result = on_result

    # ---------- 用户切换 ----------
    def on_user_change(e):
        nonlocal current_user
        current_user = user_selector.value
        refresh_data()

    user_selector.on_change = on_user_change

    # ---------- 顶部按钮栏 ----------
    top_bar = ft.Row([
        user_selector,
        ft.IconButton(icon="add", icon_size=30, on_click=add_deposit_dialog, tooltip="添加存款"),
        ft.IconButton(icon="pie_chart", icon_size=30, on_click=show_charts, tooltip="统计图表"),
        ft.PopupMenuButton(
            icon="more_vert",
            items=[
                ft.PopupMenuItem(text="用户管理", on_click=manage_users),
                ft.PopupMenuItem(text="到期提醒", on_click=check_maturities),
                ft.PopupMenuItem(text="导入数据", on_click=import_data),
                ft.PopupMenuItem(text="导出数据", on_click=export_data),
                ft.PopupMenuItem(text="导出模板", on_click=export_template),
                ft.PopupMenuItem(text="备份数据库", on_click=backup_db),
                ft.PopupMenuItem(text="恢复数据库", on_click=restore_db),
            ]
        ),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # 主界面布局
    page.add(
        top_bar,
        stats_text,
        ft.Divider(height=1),
        deposit_list,
    )

    refresh_data()

if __name__ == "__main__":
    ft.app(target=main)