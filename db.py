# -*- coding: utf-8 -*-
"""
-------------------------------------------------
Project:   DageChat (Nostr Protocol Client Research)
Author:    @BTCDage
Nostr:     npub17ahz4xa3hvkvvhh4wguzzqknp8p7l5nyzzqc3z53uq538r5qgn0q40z7pw
License:   MIT License
Source:    https://github.com/btcdage2011/DageChat
-------------------------------------------------

Disclaimer / 免责声明:
1. This software is for technical research, cryptography study, and protocol testing purposes only.
   本软件仅供计算机网络技术研究、密码学学习及协议测试使用。
2. The author assumes no liability for any misuse of this software.
   作者不对使用本软件产生的任何后果负责。
3. Illegal use of this software is strictly prohibited.
   严禁将本软件用于任何违反当地法律法规的用途。
-------------------------------------------------
"""
import sqlite3
import json
import threading
from datetime import datetime
import time

class DageDB:

    def __init__(self, db_name='dgchat.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.lock = threading.Lock()
        self._init_tables()

    def add_group_members_batch(self, group_id, member_pubkeys):
        if not member_pubkeys:
            return
        with self.lock:
            cursor = self.conn.cursor()
            try:
                ts = int(datetime.now().timestamp())
                data = [(group_id, pk, 'member', ts) for pk in member_pubkeys]
                cursor.executemany('INSERT OR IGNORE INTO group_members (group_id, member_pubkey, role, added_at) VALUES (?, ?, ?, ?)', data)
                self.conn.commit()
            except Exception as e:
                print(f'❌ Batch add members error: {e}')
            finally:
                cursor.close()

    def delete_group_completely(self, group_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
                cursor.execute('DELETE FROM group_members WHERE group_id = ?', (group_id,))
                cursor.execute('DELETE FROM group_bans WHERE group_id = ?', (group_id,))
                cursor.execute('DELETE FROM messages WHERE group_id = ?', (group_id,))
                self.conn.commit()
            finally:
                cursor.close()

    def search_messages(self, keyword, specific_target_id=None, limit=50, exclude_gid=None):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                sql = "\n                    SELECT\n                        m.id,\n                        m.group_id,\n                        m.sender_pubkey,\n                        m.content,\n                        m.created_at,\n                        COALESCE(g.group_name, c.name, 'UNKNOWN') as session_name\n                    FROM messages m\n                    LEFT JOIN groups g ON m.group_id = g.group_id\n                    LEFT JOIN contacts c ON m.group_id = c.pubkey\n                    WHERE m.content LIKE ?\n                "
                params = [f'%{keyword}%']
                if specific_target_id:
                    sql += ' AND m.group_id = ?'
                    params.append(specific_target_id)
                if exclude_gid:
                    sql += ' AND m.group_id != ?'
                    params.append(exclude_gid)
                sql += ' ORDER BY m.created_at DESC LIMIT ?'
                params.append(limit)
                cursor.execute(sql, tuple(params))
                return cursor.fetchall()
            finally:
                cursor.close()

    def get_context_around_message(self, group_id, pivot_msg_id, window=20):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT created_at FROM messages WHERE id = ?', (pivot_msg_id,))
                row = cursor.fetchone()
                if not row:
                    return ([], False, False)
                pivot_ts = row[0]
                sql_old = 'SELECT * FROM messages WHERE group_id = ? AND created_at <= ? ORDER BY created_at DESC LIMIT ?'
                cursor.execute(sql_old, (group_id, pivot_ts, window + 1))
                old_rows = cursor.fetchall()
                sql_new = 'SELECT * FROM messages WHERE group_id = ? AND created_at > ? ORDER BY created_at ASC LIMIT ?'
                cursor.execute(sql_new, (group_id, pivot_ts, window + 1))
                new_rows = cursor.fetchall()
                has_more_old = len(old_rows) > window
                has_more_new = len(new_rows) > window
                final_old = old_rows[:window]
                final_new = new_rows[:window]
                merged = final_old[::-1] + final_new
                return (merged, has_more_old, has_more_new)
            finally:
                cursor.close()

    def _get_cursor(self):
        return self.conn.cursor()

    def _init_tables(self):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('\n                    CREATE TABLE IF NOT EXISTS account (\n                        pubkey TEXT PRIMARY KEY,\n                        crypto_blob TEXT,\n                        name TEXT,\n                        picture TEXT,\n                        about TEXT,\n                        website TEXT,\n                        ln TEXT\n                    )\n                ')
                cursor.execute('\n                    CREATE TABLE IF NOT EXISTS groups (\n                        group_id TEXT PRIMARY KEY,\n                        group_name TEXT,\n                        key_hex TEXT,\n                        joined_at INTEGER,\n                        owner_pubkey TEXT,\n                        is_blocked INTEGER DEFAULT 0,\n                        last_read_at INTEGER DEFAULT 0,\n                        created_at INTEGER DEFAULT 0,\n                        type INTEGER DEFAULT 0,\n                        is_hidden INTEGER DEFAULT 0\n                    )\n                ')
                cursor.execute('\n                    CREATE TABLE IF NOT EXISTS messages (\n                        id TEXT PRIMARY KEY,\n                        group_id TEXT,\n                        sender_pubkey TEXT,\n                        content TEXT,\n                        created_at INTEGER,\n                        is_sent_by_me INTEGER DEFAULT 0,\n                        reply_to_id TEXT\n                    )\n                ')
                cursor.execute('\n                    CREATE TABLE IF NOT EXISTS contacts (\n                        pubkey TEXT PRIMARY KEY,\n                        name TEXT,\n                        enc_key TEXT,\n                        updated_at INTEGER,\n                        is_friend INTEGER DEFAULT 0,\n                        picture TEXT,\n                        about TEXT,\n                        website TEXT,\n                        ln TEXT,\n                        relays TEXT,\n                        is_blocked INTEGER DEFAULT 0,\n                        last_read_at INTEGER DEFAULT 0,\n                        is_hidden INTEGER DEFAULT 0\n                    )\n                ')
                cursor.execute("\n                    CREATE TABLE IF NOT EXISTS group_members (\n                        group_id TEXT,\n                        member_pubkey TEXT,\n                        role TEXT DEFAULT 'member',\n                        added_at INTEGER,\n                        PRIMARY KEY (group_id, member_pubkey)\n                    )\n                ")
                cursor.execute('\n                    CREATE TABLE IF NOT EXISTS group_bans (\n                        group_id TEXT,\n                        banned_pubkey TEXT,\n                        reason TEXT,\n                        created_at INTEGER,\n                        PRIMARY KEY (group_id, banned_pubkey)\n                    )\n                ')
                cursor.execute('\n                    CREATE TABLE IF NOT EXISTS system_settings (\n                        key TEXT PRIMARY KEY,\n                        value TEXT\n                    )\n                ')
                try:
                    cursor.execute('ALTER TABLE account ADD COLUMN last_broadcast_at INTEGER DEFAULT 0')
                except:
                    pass
                self.conn.commit()
            finally:
                cursor.close()

    def event_exists(self, event_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT 1 FROM messages WHERE id = ? LIMIT 1', (event_id,))
                return cursor.fetchone() is not None
            finally:
                cursor.close()

    def get_messages_grouped_for_export(self, specific_target_id=None, start_ts=0, end_ts=0, exclude_gid=None):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                sql = "\n                    SELECT\n                        m.group_id,\n                        COALESCE(g.group_name, c_session.name, 'UNKNOWN') as session_name,\n                        m.created_at,\n                        CASE\n                            WHEN m.is_sent_by_me = 1 THEN 'ME'\n                            ELSE COALESCE(c_sender.name, 'USER ' || substr(m.sender_pubkey, 1, 6))\n                        END as sender_name,\n                        m.content,\n                        m.is_sent_by_me,\n                        m.sender_pubkey,\n                        CASE\n                            WHEN g.type = 1 THEN 'ghost'\n                            WHEN g.group_id IS NOT NULL THEN 'group'\n                            ELSE 'dm'\n                        END as session_type\n                    FROM messages m\n                    LEFT JOIN contacts c_sender ON m.sender_pubkey = c_sender.pubkey\n                    LEFT JOIN groups g ON m.group_id = g.group_id\n                    LEFT JOIN contacts c_session ON m.group_id = c_session.pubkey\n                    WHERE 1=1\n                "
                params = []
                if specific_target_id:
                    sql += ' AND m.group_id = ?'
                    params.append(specific_target_id)
                if start_ts > 0:
                    sql += ' AND m.created_at >= ?'
                    params.append(start_ts)
                if end_ts > 0:
                    sql += ' AND m.created_at <= ?'
                    params.append(end_ts)
                if exclude_gid:
                    sql += ' AND m.group_id != ?'
                    params.append(exclude_gid)
                sql += ' ORDER BY m.group_id, m.created_at ASC'
                cursor.execute(sql, tuple(params))
                return cursor.fetchall()
            finally:
                cursor.close()

    def add_group_member(self, group_id, member_pubkey, role='member'):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                ts = int(datetime.now().timestamp())
                cursor.execute('INSERT OR IGNORE INTO group_members (group_id, member_pubkey, role, added_at) VALUES (?, ?, ?, ?)', (group_id, member_pubkey, role, ts))
                self.conn.commit()
            finally:
                cursor.close()

    def remove_group_member(self, group_id, member_pubkey):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('DELETE FROM group_members WHERE group_id = ? AND member_pubkey = ?', (group_id, member_pubkey))
                self.conn.commit()
            finally:
                cursor.close()

    def save_account(self, pubkey, crypto_blob_json):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('INSERT OR REPLACE INTO account (pubkey, crypto_blob) VALUES (?, ?)', (pubkey, crypto_blob_json))
                self.conn.commit()
            finally:
                cursor.close()

    def update_my_profile(self, profile_dict):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('\n                    UPDATE account SET name=?, picture=?, about=?, website=?, ln=?\n                ', (profile_dict.get('name', ''), profile_dict.get('picture', ''), profile_dict.get('about', ''), profile_dict.get('website', ''), profile_dict.get('ln', '')))
                self.conn.commit()
            finally:
                cursor.close()

    def load_account(self):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT * FROM account LIMIT 1')
                return cursor.fetchone()
            finally:
                cursor.close()

    def save_group(self, group_id, name, key_hex, owner_pubkey=None, created_at=0, group_type=0):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                timestamp = int(datetime.now().timestamp())
                if not owner_pubkey:
                    cursor.execute('SELECT owner_pubkey FROM groups WHERE group_id = ?', (group_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        owner_pubkey = row[0]
                final_created_at = created_at
                if final_created_at == 0:
                    cursor.execute('SELECT created_at FROM groups WHERE group_id = ?', (group_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        final_created_at = row[0]
                    else:
                        final_created_at = timestamp
                cursor.execute('\n                    INSERT OR IGNORE INTO groups (group_id, group_name, key_hex, joined_at, owner_pubkey, is_blocked, last_read_at, created_at, type)\n                    VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)\n                ', (group_id, name, key_hex, timestamp, owner_pubkey, timestamp, final_created_at, group_type))
                cursor.execute('\n                    UPDATE groups\n                    SET key_hex=?, owner_pubkey=?, created_at=?, is_blocked=0, type=?\n                    WHERE group_id=?\n                ', (key_hex, owner_pubkey, final_created_at, group_type, group_id))
                self.conn.commit()
            finally:
                cursor.close()

    def add_group_ban(self, group_id, banned_pubkey, reason=''):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                ts = int(datetime.now().timestamp())
                cursor.execute('INSERT OR REPLACE INTO group_bans (group_id, banned_pubkey, reason, created_at) VALUES (?, ?, ?, ?)', (group_id, banned_pubkey, reason, ts))
                self.conn.commit()
            finally:
                cursor.close()

    def remove_group_ban(self, group_id, banned_pubkey):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('DELETE FROM group_bans WHERE group_id = ? AND banned_pubkey = ?', (group_id, banned_pubkey))
                self.conn.commit()
            finally:
                cursor.close()

    def is_banned_in_group(self, group_id, pubkey):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT is_blocked FROM contacts WHERE pubkey = ?', (pubkey,))
                row = cursor.fetchone()
                if row and row[0] == 1:
                    return True
                cursor.execute('SELECT 1 FROM group_bans WHERE group_id = ? AND banned_pubkey = ?', (group_id, pubkey))
                if cursor.fetchone():
                    return True
                return False
            finally:
                cursor.close()

    def get_group_ban_list(self, group_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT banned_pubkey, reason FROM group_bans WHERE group_id = ?', (group_id,))
                return cursor.fetchall()
            finally:
                cursor.close()

    def update_group_name_local(self, group_id, new_name):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (new_name, group_id))
                self.conn.commit()
            finally:
                cursor.close()

    def block_group(self, group_id, blocked=True):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                val = 1 if blocked else 0
                cursor.execute('UPDATE groups SET is_blocked = ? WHERE group_id = ?', (val, group_id))
                self.conn.commit()
            finally:
                cursor.close()

    def is_group_blocked(self, group_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT is_blocked FROM groups WHERE group_id = ?', (group_id,))
                row = cursor.fetchone()
                return row and row[0] == 1
            finally:
                cursor.close()

    def get_group_owner(self, group_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT owner_pubkey FROM groups WHERE group_id = ?', (group_id,))
                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                cursor.close()

    def get_group(self, group_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
                return cursor.fetchone()
            finally:
                cursor.close()

    def get_all_groups(self):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT * FROM groups')
                return cursor.fetchall()
            finally:
                cursor.close()

    def save_message(self, msg_id, group_id, sender_pk, content, created_at, is_me, reply_to_id=None, fail_content=None):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                final_ts = created_at
                actual_content = fail_content if fail_content is not None else content
                cursor.execute('INSERT OR IGNORE INTO messages VALUES (?, ?, ?, ?, ?, ?, ?)', (msg_id, group_id, sender_pk, actual_content, final_ts, 1 if is_me else 0, reply_to_id))
                cursor.execute('UPDATE groups SET is_hidden = 0 WHERE group_id = ?', (group_id,))
                cursor.execute('UPDATE contacts SET is_hidden = 0 WHERE pubkey = ?', (group_id,))
                self.conn.commit()
            except sqlite3.IntegrityError:
                pass
            finally:
                cursor.close()

    def delete_message(self, msg_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
                self.conn.commit()
            finally:
                cursor.close()

    def update_message_content(self, msg_id, new_content):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('UPDATE messages SET content = ? WHERE id = ?', (new_content, msg_id))
                self.conn.commit()
            finally:
                cursor.close()

    def get_message(self, msg_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT * FROM messages WHERE id = ?', (msg_id,))
                return cursor.fetchone()
            finally:
                cursor.close()

    def get_history(self, group_id, limit=50, before_ts=None):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                sql = 'SELECT * FROM messages WHERE group_id = ?'
                params = [group_id]
                if before_ts:
                    sql += ' AND created_at < ?'
                    params.append(before_ts)
                sql += ' ORDER BY created_at DESC LIMIT ?'
                params.append(limit)
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
                return rows[::-1]
            finally:
                cursor.close()

    def get_last_timestamp(self, filter_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT MAX(created_at) FROM messages WHERE group_id = ?', (filter_id,))
                row = cursor.fetchone()
                return int(row[0]) if row and row[0] else 0
            finally:
                cursor.close()

    def save_contact(self, pubkey, name, enc_key=None, is_friend=None, extra_info=None):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                timestamp = int(datetime.now().timestamp())
                cursor.execute('SELECT enc_key, name, is_friend, is_blocked, last_read_at, picture, about, website, ln, relays FROM contacts WHERE pubkey = ?', (pubkey,))
                row = cursor.fetchone()
                final_name = name if name else row[1] if row else ''
                final_enc = enc_key if enc_key else row[0] if row else ''
                final_is_friend = is_friend if is_friend is not None else row[2] if row else 0
                final_is_blocked = row[3] if row else 0
                final_last_read = row[4] if row else 0
                new_pic = extra_info.get('picture') if extra_info else None
                old_pic = row[5] if row else None
                final_pic = new_pic if new_pic else old_pic
                new_abt = extra_info.get('about') if extra_info else None
                old_abt = row[6] if row else ''
                final_abt = new_abt if new_abt else old_abt
                new_web = extra_info.get('website') if extra_info else None
                old_web = row[7] if row else ''
                final_web = new_web if new_web else old_web
                new_ln = extra_info.get('ln') if extra_info else None
                old_ln = row[8] if row else ''
                final_ln = new_ln if new_ln else old_ln
                new_rel = extra_info.get('relays') if extra_info else None
                old_rel = row[9] if row else ''
                final_rel = new_rel if new_rel else old_rel
                if row:
                    cursor.execute('\n                        UPDATE contacts\n                        SET updated_at=?, name=?, enc_key=?, is_friend=?,\n                            picture=?, about=?, website=?, ln=?, relays=?\n                        WHERE pubkey=?\n                    ', (timestamp, final_name, final_enc, final_is_friend, final_pic, final_abt, final_web, final_ln, final_rel, pubkey))
                else:
                    cursor.execute('\n                        INSERT INTO contacts (pubkey, name, enc_key, updated_at, is_friend, is_blocked, last_read_at, picture, about, website, ln, relays)\n                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n                    ', (pubkey, final_name, final_enc, timestamp, final_is_friend, final_is_blocked, final_last_read, final_pic, final_abt, final_web, final_ln, final_rel))
                self.conn.commit()
            finally:
                cursor.close()

    def get_blocked_contacts(self):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT pubkey, name FROM contacts WHERE is_blocked = 1')
                return [{'pubkey': r[0], 'name': r[1]} for r in cursor.fetchall()]
            finally:
                cursor.close()

    def block_contact(self, pubkey, blocked=True):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                val = 1 if blocked else 0
                cursor.execute('UPDATE contacts SET is_blocked = ? WHERE pubkey = ?', (val, pubkey))
                self.conn.commit()
            finally:
                cursor.close()

    def is_blocked(self, pubkey):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT is_blocked FROM contacts WHERE pubkey = ?', (pubkey,))
                row = cursor.fetchone()
                return row and row[0] == 1
            finally:
                cursor.close()

    def get_contact_info(self, pubkey):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('\n                    SELECT pubkey, name, enc_key, updated_at, is_friend, is_blocked,\n                           picture, about, website, ln, relays\n                    FROM contacts WHERE pubkey = ?\n                ', (pubkey,))
                return cursor.fetchone()
            finally:
                cursor.close()

    def get_group_members(self, group_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT member_pubkey FROM group_members WHERE group_id = ?', (group_id,))
                rows = cursor.fetchall()
                if rows:
                    return [r[0] for r in rows]
                cursor.execute('SELECT DISTINCT sender_pubkey FROM messages WHERE group_id = ?', (group_id,))
                return [r[0] for r in cursor.fetchall()]
            finally:
                cursor.close()

    def get_contact_name(self, pubkey):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT name FROM contacts WHERE pubkey = ?', (pubkey,))
                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                cursor.close()

    def get_contact_enc_key(self, pubkey):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT enc_key FROM contacts WHERE pubkey = ?', (pubkey,))
                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                cursor.close()

    def is_friend(self, pubkey):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT is_friend FROM contacts WHERE pubkey = ?', (pubkey,))
                row = cursor.fetchone()
                return row and row[0] == 1
            finally:
                cursor.close()

    def get_all_contacts(self):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT pubkey, name, enc_key, is_friend FROM contacts')
                return [{'pubkey': r[0], 'name': r[1], 'enc_key': r[2], 'is_friend': r[3]} for r in cursor.fetchall()]
            finally:
                cursor.close()

    def mark_read(self, target_id, is_group):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                now = int(time.time())
                if is_group:
                    cursor.execute('UPDATE groups SET last_read_at = ? WHERE group_id = ?', (now, target_id))
                else:
                    cursor.execute('UPDATE contacts SET last_read_at = ? WHERE pubkey = ?', (now, target_id))
                self.conn.commit()
            except Exception as e:
                print(f'❌ [DB] 标记已读失败: {e}')
            finally:
                cursor.close()

    def get_session_list(self):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                query = "\n                    SELECT\n                        id, name, type,\n                        MAX(msg_time) as last_time,\n                        SUM(\n                            CASE\n                                WHEN msg_time > COALESCE(last_read_at, 0) AND is_sent_by_me = 0\n                                THEN 1\n                                ELSE 0\n                            END\n                        ) as unread\n                    FROM (\n                        -- 1. 群组数据 (排除掉那些 ID 也是联系人的行)\n                        SELECT\n                            g.group_id as id,\n                            g.group_name as name,\n                            'group' as type,\n                            g.last_read_at,\n                            m.created_at as msg_time,\n                            m.is_sent_by_me\n                        FROM groups g\n                        LEFT JOIN messages m ON m.group_id = g.group_id\n                        WHERE g.is_hidden = 0\n                          AND g.group_id NOT IN (SELECT pubkey FROM contacts)\n\n                        UNION ALL\n\n                        -- 2. 私聊数据\n                        SELECT\n                            c.pubkey as id,\n                            c.name,\n                            'dm' as type,\n                            c.last_read_at,\n                            m.created_at as msg_time,\n                            m.is_sent_by_me\n                        FROM contacts c\n                        LEFT JOIN messages m ON m.group_id = c.pubkey\n                        WHERE (c.is_friend = 1 OR m.id IS NOT NULL)\n                          AND c.is_hidden = 0\n                    )\n                    GROUP BY id\n                    ORDER BY last_time DESC\n                "
                cursor.execute(query)
                results = []
                for r in cursor.fetchall():
                    results.append({'id': r[0], 'name': r[1] if r[1] else '未知', 'type': r[2], 'last_time': r[3] if r[3] else 0, 'unread': r[4] if r[4] else 0})
                return results
            finally:
                cursor.close()

    def set_session_hidden(self, target_id, is_group, hidden=True):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                val = 1 if hidden else 0
                if is_group:
                    cursor.execute('UPDATE groups SET is_hidden = ? WHERE group_id = ?', (val, target_id))
                else:
                    cursor.execute('UPDATE contacts SET is_hidden = ? WHERE pubkey = ?', (val, target_id))
                self.conn.commit()
            finally:
                cursor.close()

    def clear_chat_history(self, target_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('DELETE FROM messages WHERE group_id = ?', (target_id,))
                self.conn.commit()
            finally:
                cursor.close()

    def get_friends(self):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT pubkey, name, enc_key FROM contacts WHERE is_friend = 1 ORDER BY name')
                return [{'pubkey': r[0], 'name': r[1], 'enc_key': r[2]} for r in cursor.fetchall()]
            finally:
                cursor.close()

    def get_gallery_images(self, chat_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT id, content FROM messages WHERE group_id = ? ORDER BY created_at ASC', (chat_id,))
                rows = cursor.fetchall()
                image_list = []
                for r in rows:
                    msg_id, content = (r[0], r[1])
                    if content and content.startswith('{') and ('"image":' in content):
                        try:
                            data = json.loads(content)
                            if data.get('image'):
                                image_list.append({'id': msg_id, 'image_b64': data['image']})
                        except:
                            pass
                return image_list
            finally:
                cursor.close()

    def get_pubkey_by_enc_key(self, enc_key):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT pubkey FROM contacts WHERE enc_key = ?', (enc_key,))
                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                cursor.close()

    def has_chat_history(self, chat_id):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT 1 FROM messages WHERE group_id = ? LIMIT 1', (chat_id,))
                return cursor.fetchone() is not None
            finally:
                cursor.close()

    def get_messages_for_export(self, target_id=None):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                sql = "\n                    SELECT\n                        datetime(m.created_at, 'unixepoch', 'localtime') as time,\n                        CASE\n                            WHEN m.is_sent_by_me = 1 THEN '我'\n                            ELSE coalesce(c.name, '用户 ' || substr(m.sender_pubkey, 1, 6))\n                        END as sender,\n                        m.content,\n                        m.group_id\n                    FROM messages m\n                    LEFT JOIN contacts c ON c.pubkey = m.sender_pubkey\n                "
                params = ()
                if target_id:
                    sql += ' WHERE m.group_id = ?'
                    params = (target_id,)
                sql += ' ORDER BY m.created_at ASC'
                cursor.execute(sql, params)
                return cursor.fetchall()
            finally:
                cursor.close()

    def get_messages_after_timestamp(self, group_id, after_ts):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                sql = 'SELECT * FROM messages WHERE group_id = ? AND created_at > ? ORDER BY created_at ASC'
                cursor.execute(sql, (group_id, after_ts))
                return cursor.fetchall()
            finally:
                cursor.close()

    def get_last_broadcast_time(self):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT last_broadcast_at FROM account LIMIT 1')
                row = cursor.fetchone()
                return row[0] if row and row[0] else 0
            except:
                return 0
            finally:
                cursor.close()

    def update_last_broadcast_time(self, ts=None):
        if ts is None:
            ts = int(time.time())
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('UPDATE account SET last_broadcast_at = ?', (ts,))
                self.conn.commit()
            finally:
                cursor.close()

    def get_setting(self, key, default=None):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT value FROM system_settings WHERE key = ?', (key,))
                row = cursor.fetchone()
                return row[0] if row else default
            finally:
                cursor.close()

    def set_setting(self, key, value):
        with self.lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute('INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)', (key, str(value)))
                self.conn.commit()
            finally:
                cursor.close()

    def delete_messages_batch(self, msg_ids):
        if not msg_ids:
            return 0
        with self.lock:
            cursor = self.conn.cursor()
            try:
                placeholders = ','.join(('?' for _ in msg_ids))
                sql = f'DELETE FROM messages WHERE id IN ({placeholders})'
                cursor.execute(sql, tuple(msg_ids))
                self.conn.commit()
                return cursor.rowcount
            except Exception as e:
                print(f'❌ [DB] Batch delete messages error: {e}')
                return 0
            finally:
                cursor.close()
