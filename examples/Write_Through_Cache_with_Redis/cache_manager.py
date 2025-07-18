#!/usr/bin/env python3

import sqlite3
import redis
import json
import time
import threading
from typing import Any, Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor
from config import REDIS_CONFIG, SQLITE_CONFIG, DEMO_CONFIG


class WriteThoughCacheManager:
    
    def __init__(self):
        self.redis_client = None
        self.sqlite_conn = None
        self.write_queue = []
        self.write_lock = threading.Lock()
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'total_reads': 0,
            'total_writes': 0,
            'batch_writes': 0
        }
        
    def connect(self):
        try:
            # redis first
            self.redis_client = redis.Redis(**REDIS_CONFIG)
            self.redis_client.ping()
            print("Connected to Redis successfully")
            self._log_redis_connection()
            
            # then sqlite
            db_path = SQLITE_CONFIG['database_path']
            print(f"[DEBUG] Connecting to SQLite database: {db_path}")
            
            self.sqlite_conn = sqlite3.connect(
                db_path,
                timeout=SQLITE_CONFIG['timeout'],
                check_same_thread=False
            )
            self.sqlite_conn.row_factory = sqlite3.Row
            
            # speed things up
            self.sqlite_conn.execute("PRAGMA journal_mode=WAL")
            self.sqlite_conn.execute("PRAGMA synchronous=NORMAL")
            self.sqlite_conn.execute("PRAGMA cache_size=10000")
            self.sqlite_conn.execute("PRAGMA temp_store=memory")
            
            print("Connected to SQLite successfully")
            self._initialize_database()
            
        except redis.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect to SQLite: {e}")
    
    def _log_redis_connection(self):
        try:
            connection_id = f"zos_demo_connection_{int(time.time())}"
            self.redis_client.set(f"connection:marker:{connection_id}", "DEMO_STARTED", ex=60)
            
            info = self.redis_client.info()
            print("Redis Server Info:")
            print(f"   Version: {info.get('redis_version', 'unknown')}")
            print(f"   Port: {REDIS_CONFIG['port']}")
            print(f"   Connected clients: {info.get('connected_clients', 0)}")
            print(f"   Total commands processed: {info.get('total_commands_processed', 0)}")
            
            self.redis_client.set("demo:status", "z/OS_WRITE_THROUGH_CACHE_DEMO_ACTIVE", ex=3600)
            self.redis_client.set("demo:timestamp", str(time.time()), ex=3600)
            self.redis_client.set("demo:config", f"port_{REDIS_CONFIG['port']}", ex=3600)
            
            print("Redis activity markers set - check your Redis server terminal for commands!")
            
        except Exception as e:
            print(f"Warning: Could not set Redis activity markers: {e}")
    
    def _initialize_database(self):
        cursor = self.sqlite_conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                profile_data TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                description TEXT,
                stock_quantity INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                execution_time REAL NOT NULL,
                cache_used BOOLEAN DEFAULT FALSE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.sqlite_conn.commit()
        print("Database schema initialized")
    
    def _generate_cache_key(self, table: str, key: Union[str, int]) -> str:
        return f"{table}:{key}"
    
    def get(self, table: str, key: Union[str, int]) -> Optional[Dict]:
        start_time = time.time()
        cache_key = self._generate_cache_key(table, key)
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.stats['cache_hits'] += 1
                self.stats['total_reads'] += 1
                self._log_performance('read', time.time() - start_time, True)
                return json.loads(cached_data)
            
            self.stats['cache_misses'] += 1
            self.stats['total_reads'] += 1
            
            cursor = self.sqlite_conn.cursor()
            cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (key,))
            row = cursor.fetchone()
            
            if row:
                data = dict(row)
                
                self.redis_client.setex(
                    cache_key, 
                    DEMO_CONFIG['cache_ttl'], 
                    json.dumps(data, default=str)
                )
                
                self._log_performance('read', time.time() - start_time, False)
                return data
            
            self._log_performance('read', time.time() - start_time, False)
            return None
            
        except Exception as e:
            print(f"Error during get operation: {e}")
            return None
    
    def set(self, table: str, data: Dict, key_field: str = 'id') -> bool:
        start_time = time.time()
        
        try:
            with self.write_lock:
                cursor = self.sqlite_conn.cursor()
                
                db_data = data.copy()
                
                if table == 'users' and 'username' in db_data:
                    print(f"[DEBUG] Attempting to insert user: {db_data['username']}")
                
                if key_field in db_data and (db_data[key_field] is None or db_data[key_field] == ''):
                    del db_data[key_field]
                
                if 'id' in db_data and key_field != 'id':
                    del db_data['id']
                
                columns = list(db_data.keys())
                placeholders = ['?' for _ in columns]
                values = [db_data[col] for col in columns]
                
                query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                
                if table == 'users':
                    print(f"[DEBUG] SQL Query: {query}")
                    print(f"[DEBUG] Values: {values[:2]}...")  # first 2 values only
                    
                    if 'username' in db_data:
                        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (db_data['username'],))
                        existing_count = cursor.fetchone()[0]
                        if existing_count > 0:
                            print(f"[ERROR] Username {db_data['username']} already exists in database!")
                            cursor.execute("SELECT username FROM users LIMIT 5")
                            existing_users = cursor.fetchall()
                            print(f"[DEBUG] Current usernames in DB: {[user[0] for user in existing_users]}")
                            return False
                
                cursor.execute(query, values)
                
                record_id = cursor.lastrowid
                
                self.sqlite_conn.commit()
                
                # put in cache too (don't modify original)
                cache_data = data.copy()
                cache_data[key_field] = record_id
                
                cache_key = self._generate_cache_key(table, record_id)
                self.redis_client.setex(
                    cache_key,
                    DEMO_CONFIG['cache_ttl'],
                    json.dumps(cache_data, default=str)
                )
                
                self.stats['total_writes'] += 1
                self._log_performance('write', time.time() - start_time, True)
                
                return True
                
        except Exception as e:
            print(f"Error during write operation: {e}")
            return False
    
    def batch_write(self, table: str, data_list: List[Dict]) -> int:
        start_time = time.time()
        successful_writes = 0
        
        try:
            with self.write_lock:
                cursor = self.sqlite_conn.cursor()
                
                for data in data_list:
                    try:
                        db_data = data.copy()
                        
                        if 'id' in db_data and (db_data['id'] is None or db_data['id'] == ''):
                            del db_data['id']
                        
                        if 'id' in db_data:
                            del db_data['id']
                        
                        columns = list(db_data.keys())
                        placeholders = ['?' for _ in columns]
                        values = [db_data[col] for col in columns]
                        
                        query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                        cursor.execute(query, values)
                        
                        record_id = cursor.lastrowid
                        
                        cache_data = data.copy()
                        cache_data['id'] = record_id
                        
                        cache_key = self._generate_cache_key(table, record_id)
                        self.redis_client.setex(
                            cache_key,
                            DEMO_CONFIG['cache_ttl'],
                            json.dumps(cache_data, default=str)
                        )
                        
                        successful_writes += 1
                        
                    except Exception as e:
                        print(f"Error writing record: {e}")
                        continue
                
                self.sqlite_conn.commit()
                
                self.stats['total_writes'] += successful_writes
                self.stats['batch_writes'] += 1
                self._log_performance('batch_write', time.time() - start_time, True)
                
                return successful_writes
                
        except Exception as e:
            print(f"Error during batch write: {e}")
            return successful_writes
    
    def _log_performance(self, operation_type: str, execution_time: float, cache_used: bool):
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute(
                "INSERT INTO performance_log (operation_type, execution_time, cache_used) VALUES (?, ?, ?)",
                (operation_type, execution_time, cache_used)
            )
            self.sqlite_conn.commit()
        except Exception:
            pass
    
    def get_cache_stats(self) -> Dict:
        total_reads = self.stats['total_reads']
        hit_ratio = (self.stats['cache_hits'] / total_reads * 100) if total_reads > 0 else 0
        
        return {
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'total_reads': total_reads,
            'total_writes': self.stats['total_writes'],
            'batch_writes': self.stats['batch_writes'],
            'hit_ratio_percent': hit_ratio
        }
    
    def clear_cache(self):
        try:
            # clear all demo-related keys
            keys = self.redis_client.keys("users:*")
            keys.extend(self.redis_client.keys("products:*"))
            keys.extend(self.redis_client.keys("demo:*"))
            
            if keys:
                self.redis_client.delete(*keys)
            
            self.stats = {
                'cache_hits': 0,
                'cache_misses': 0,
                'total_reads': 0,
                'total_writes': 0,
                'batch_writes': 0
            }
            
        except Exception as e:
            print(f"Error clearing cache: {e}")
    
    def close(self):
        try:
            if self.redis_client:
                self.redis_client.close()
            if self.sqlite_conn:
                self.sqlite_conn.close()
        except Exception as e:
            print(f"Error closing connections: {e}") 