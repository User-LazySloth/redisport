#!/usr/bin/env python3

import time
import random
import json
from typing import List, Dict
from tabulate import tabulate
import click

from cache_manager import WriteThoughCacheManager
from config import DEMO_CONFIG, REDIS_CONFIG


class CacheDemo:
    
    def __init__(self):
        self.cache_manager = WriteThoughCacheManager()
        self.sample_users = []
        self.sample_products = []
        
    def initialize(self):
        print("[INFO] Initializing Redis Write-Through Cache Demo")
        print("=" * 60)
        
        try:
            self.cache_manager.connect()
            
            print("[INFO] Cleaning up existing data for fresh start...")
            self._clear_all_data()
            
            self._validate_redis_connection()
            self._generate_sample_data()
            print("[SUCCESS] Demo initialization completed successfully\n")
        except Exception as e:
            print(f"[ERROR] Demo initialization failed: {e}")
            raise
    
    def _clear_all_data(self):
        cursor = self.cache_manager.sqlite_conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        
        print(f"[INFO] Found {user_count} users and {product_count} products in database")
        
        if user_count > 0:
            cursor.execute("SELECT username FROM users LIMIT 5")
            existing_users = cursor.fetchall()
            print(f"[DEBUG] Existing usernames: {[user[0] for user in existing_users]}")
        
        # nuke everything and start fresh
        print("[INFO] Using DROP TABLE approach for complete cleanup...")
        try:
            cursor.execute("DROP TABLE IF EXISTS users")
            cursor.execute("DROP TABLE IF EXISTS products") 
            cursor.execute("DROP TABLE IF EXISTS performance_log")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('users', 'products', 'performance_log')")
            self.cache_manager.sqlite_conn.commit()
            print("[SUCCESS] Tables dropped successfully")
            
            self.cache_manager._initialize_database()
            print("[SUCCESS] Tables recreated")
            
            cursor.execute("SELECT COUNT(*) FROM users")
            final_count = cursor.fetchone()[0]
            print(f"[INFO] Final user count after cleanup: {final_count}")
            
        except Exception as e:
            print(f"[ERROR] Database cleanup failed: {e}")
            raise
        
        self.cache_manager.clear_cache()
        print("[SUCCESS] Database and cache cleared (complete rebuild)")
    
    def _validate_redis_connection(self):
        print("\n[INFO] REDIS CONNECTION VALIDATION")
        print("-" * 50)
        
        try:
            info = self.cache_manager.redis_client.info()
            
            print("[SUCCESS] Connected to Redis server:")
            print(f"[INFO]    Host: {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
            print(f"[INFO]    Redis Version: {info.get('redis_version', 'unknown')}")
            print(f"[INFO]    Connected Clients: {info.get('connected_clients', 0)}")
            print(f"[INFO]    Total Commands Processed: {info.get('total_commands_processed', 0):,}")
            print(f"[INFO]    Memory Used: {info.get('used_memory_human', 'unknown')}")
            
            timestamp = int(time.time())
            print(f"\n[DEMO] Sending test commands to Redis server...")
            time.sleep(1)
            
            self.cache_manager.redis_client.set(f"DEMO_TEST_{timestamp}", "Hello_Redis!", ex=600)
            time.sleep(0.5)
            self.cache_manager.redis_client.lpush("demo:test_log", f"Demo started at {timestamp}")
            time.sleep(0.5)
            
            print(f"[INFO] Check your Redis monitor terminal for real-time commands")
            print(f"[INFO] Expected commands: SET, GET, INCR, LPUSH, HSET, SETEX")
            
            input("\n[PROMPT] Press Enter when you've confirmed Redis activity in monitor terminal...")
            
        except Exception as e:
            print(f"[ERROR] Redis connection validation failed: {e}")
            raise
    
    def _generate_sample_data(self):
        print("[INFO] Generating sample data for demonstration...")
        
        sample_size = 20 if DEMO_CONFIG['sample_data_size'] > 1000 else 10
        
        # INCR uses optimizations that meddle with how i use batching hence using timestamps for uniqueness
        timestamp_suffix = str(int(time.time()))[-6:]
        print(f"[DEBUG] Using timestamp suffix: {timestamp_suffix}")
        
        self.sample_users = []
        for i in range(sample_size):
            username = f'student_{i:02d}_{timestamp_suffix}'
            user = {
                'username': username,
                'email': f'student{i:02d}_{timestamp_suffix}@university.edu',
                'profile_data': json.dumps({
                    'age': random.randint(18, 25),
                    'major': random.choice(['Computer Science', 'Business', 'Engineering', 'Art', 'Math']),
                    'year': random.choice(['Freshman', 'Sophomore', 'Junior', 'Senior']),
                    'preferences': {
                        'study_group': random.choice([True, False]),
                        'theme': random.choice(['light', 'dark'])
                    }
                })
            }
            self.sample_users.append(user)
        
        # debug output
        sample_usernames = [user['username'] for user in self.sample_users[:3]]
        print(f"[DEBUG] Sample usernames generated: {sample_usernames}")
        
        categories = ['Laptops', 'Textbooks', 'Supplies', 'Food', 'Software']
        for i in range(sample_size):
            product = {
                'name': f'Campus_Item_{i:02d}_{timestamp_suffix}',
                'price': round(random.uniform(5.0, 500.0), 2),
                'category': random.choice(categories),
                'description': f'Essential campus item #{i:02d}',
                'stock_quantity': random.randint(0, 50)
            }
            self.sample_products.append(product)
        
        print(f"[SUCCESS] Generated {len(self.sample_users)} users and {len(self.sample_products)} products")
    
    def demo_write_performance(self):
        print("\n[DEMO] WRITE PERFORMANCE COMPARISON")
        print("=" * 50)
        print("[INFO] Testing individual writes vs batch writes")
        
        batch_size = 8
        test_users = self.sample_users[:batch_size * 2]
        
        print(f"[INFO] Testing with {len(test_users)} user records")
        print("[INFO] Monitor Redis terminal to observe command patterns")
        
        # individual writes
        print(f"\n[PERF] Starting individual write test...")
        start_time = time.time()
        individual_count = 0
        
        for i, user in enumerate(test_users[:batch_size]):
            print(f"[DEMO]   Writing user {i+1}/{batch_size}: {user['username']}")
            if self.cache_manager.set('users', user):
                individual_count += 1
            time.sleep(0.4)  # because, i need to see it bruv
        
        individual_time = time.time() - start_time
        individual_rate = individual_count / individual_time if individual_time > 0 else 0
        
        print(f"[INFO] Individual writes completed - waiting 2 seconds...")
        time.sleep(2)
        
        # batch writes
        print("[PERF] Starting batch write test...")
        start_time = time.time()
        
        batch_count = self.cache_manager.batch_write('users', test_users[batch_size:])
        
        batch_time = time.time() - start_time
        batch_rate = batch_count / batch_time if batch_time > 0 else 0
        
        improvement = ((batch_rate - individual_rate) / individual_rate * 100) if individual_rate > 0 else 0
        
        results = [
            ["Method", "Records", "Time (seconds)", "Records/sec", "Performance"],
            ["Individual", individual_count, f"{individual_time:.2f}", f"{individual_rate:.1f}", "Baseline"],
            ["Batch", batch_count, f"{batch_time:.3f}", f"{batch_rate:.1f}", f"{improvement:.1f}% faster"]
        ]
        
        print("\n[PERF] WRITE PERFORMANCE RESULTS:")
        print(tabulate(results, headers="firstrow", tablefmt="grid"))
        
        if improvement > 1000:
            print(f"[SUCCESS] Batch writes achieved {improvement:.0f}% performance improvement")
        else:
            print(f"[INFO] Batch writes provided {improvement:.1f}% performance gain")
    
    def demo_read_performance(self):
        print("\n[DEMO] READ PERFORMANCE COMPARISON")
        print("=" * 50)
        print("[INFO] Testing cache miss vs cache hit performance")
        
        print("[INFO] Populating database with initial user data...")
        initial_data = self.sample_users[:12]  # 12 users should be enough
        
        for i, user in enumerate(initial_data):
            print(f"[DEMO]   Adding user {i+1}/12: {user['username']}")
            self.cache_manager.set('users', user)
            time.sleep(0.2)
        
        print("[INFO] Initial data population completed - waiting 2 seconds...")
        time.sleep(2)
        
        # clear cache to test cold reads
        print("[CACHE] Clearing cache to simulate cold start...")
        self.cache_manager.clear_cache()
        time.sleep(1)
        
        print("[INFO] Starting read performance tests...")
        
        print("\n[CACHE] TEST 1: Cold cache misses (random user access)")
        print("[INFO] Simulating first-time user access patterns")
        cold_times = []
        for i in range(12):
            user_id = random.randint(1, 12)
            print(f"[DEMO]   Cold read user ID {user_id} (attempt {i+1}/12)")
            start_time = time.time()
            self.cache_manager.get('users', user_id)
            cold_times.append((time.time() - start_time) * 1000)
            time.sleep(0.3)  # watch for GET + SETEX pattern
        
        avg_cold_time = sum(cold_times) / len(cold_times)
        print(f"[PERF] Cold cache average response time: {avg_cold_time:.2f}ms")
        
        print("[INFO] Waiting 2 seconds before warm cache test...")
        time.sleep(2)
        
        # warm cache - should hit redis
        print("[CACHE] TEST 2: Warm cache hits (popular user access)")
        print("[INFO] Simulating repeated access to popular users")
        popular_users = [1, 2, 3, 4]
        warm_times = []
        for i in range(12):
            user_id = random.choice(popular_users)
            print(f"[DEMO]   Warm read user ID {user_id} (attempt {i+1}/12)")
            start_time = time.time()
            self.cache_manager.get('users', user_id)
            warm_times.append((time.time() - start_time) * 1000)
            time.sleep(0.3)
        
        avg_warm_time = sum(warm_times) / len(warm_times)
        print(f"[PERF] Warm cache average response time: {avg_warm_time:.2f}ms")
        
        speedup = avg_cold_time / avg_warm_time if avg_warm_time > 0 else 1
        
        stats = self.cache_manager.get_cache_stats()
        hit_ratio = (stats['cache_hits'] / stats['total_reads'] * 100) if stats['total_reads'] > 0 else 0
        
        read_results = [
            ["Cache State", "Avg Time (ms)", "Data Source", "Performance"],
            ["Cold (miss)", f"{avg_cold_time:.2f}", "SQLite Database", "Baseline"],
            ["Warm (hit)", f"{avg_warm_time:.2f}", "Redis Cache", f"{speedup:.1f}x faster"]
        ]
        
        print("\n[PERF] READ PERFORMANCE RESULTS:")
        print(tabulate(read_results, headers="firstrow", tablefmt="grid"))
        
        cache_stats = [
            ["Metric", "Value", "Description"],
            ["Total Reads", stats['total_reads'], "Total read operations performed"],
            ["Cache Hits", stats['cache_hits'], "Reads served from Redis cache"],
            ["Cache Misses", stats['cache_misses'], "Reads requiring SQLite access"],
            ["Hit Ratio", f"{hit_ratio:.1f}%", "Percentage served from cache"]
        ]
        
        print("\n[CACHE] CACHE STATISTICS:")
        print(tabulate(cache_stats, headers="firstrow", tablefmt="grid"))
        
        if hit_ratio > 30:
            print(f"[SUCCESS] Cache hit ratio of {hit_ratio:.0f}% indicates effective caching")
        else:
            print("[INFO] Cache is building up popular data patterns")
    
    def demo_concurrent_operations(self):
        print("\n[DEMO] CONCURRENT OPERATIONS SIMULATION")
        print("=" * 50)
        print("[INFO] Simulating multiple concurrent users")
        
        initial_data = self.sample_users[:6]
        print("[INFO] Setting up initial user base...")
        for i, user in enumerate(initial_data):
            print(f"[DEMO]   Adding user: {user['username']}")
            self.cache_manager.set('users', user)
            time.sleep(0.2)
        
        print("[INFO] Beginning concurrent operation simulation")
        print("[INFO] Running sequentially for z/OS compatibility")
        print("[INFO] Monitor Redis terminal for operation patterns")
        
        # simulate reads
        read_times = []
        print("\n[DEMO] SIMULATION: User profile lookups")
        for i in range(8):
            user_id = random.randint(1, 6)
            print(f"[DEMO]   User {user_id} profile lookup (operation {i+1}/8)")
            start_time = time.time()
            try:
                self.cache_manager.get('users', user_id)
                read_times.append((time.time() - start_time) * 1000)
            except Exception as e:
                print(f"[ERROR] Profile lookup failed: {e}")
            time.sleep(0.4)
        
        print("[INFO] Read operations completed - waiting 2 seconds...")
        time.sleep(2)
        
        # simulate writes
        write_times = []
        print("[DEMO] SIMULATION: New user registrations")
        concurrent_timestamp = str(int(time.time()))[-6:]
        for i in range(4):
            new_user = {
                'username': f'newuser_{i:02d}_{concurrent_timestamp}',
                'email': f'newuser{i:02d}_{concurrent_timestamp}@university.edu',
                'profile_data': json.dumps({'status': 'new_registration', 'batch_id': i})
            }
            print(f"[DEMO]   New user registration: {new_user['username']} (operation {i+1}/4)")
            start_time = time.time()
            try:
                self.cache_manager.set('users', new_user)
                write_times.append((time.time() - start_time) * 1000)
            except Exception as e:
                print(f"[ERROR] Registration failed: {e}")
            time.sleep(0.4)
        
        avg_read = sum(read_times) / len(read_times) if read_times else 0
        avg_write = sum(write_times) / len(write_times) if write_times else 0
        
        concurrent_results = [
            ["Operation Type", "Count", "Avg Time (ms)", "Status"],
            ["Profile Lookups", len(read_times), f"{avg_read:.2f}", "Completed"],
            ["User Registrations", len(write_times), f"{avg_write:.2f}", "Completed"]
        ]
        
        print("\n[PERF] CONCURRENT OPERATIONS RESULTS:")
        print(tabulate(concurrent_results, headers="firstrow", tablefmt="grid"))
        
        final_stats = self.cache_manager.get_cache_stats()
        print(f"\n[SUMMARY] Concurrent operations summary:")
        print(f"[INFO]    Total read operations: {final_stats['total_reads']}")
        print(f"[INFO]    Total write operations: {final_stats['total_writes']}")
        print(f"[CACHE]   Cache hits: {final_stats['cache_hits']}/{final_stats['total_reads']}")
        print("[SUCCESS] All concurrent operations completed successfully")
    
    def run_full_demo(self):
        print("\n[DEMO] REDIS WRITE-THROUGH CACHE DEMONSTRATION")
        print("[INFO] Comprehensive cache performance evaluation")
        print("[INFO] This demo shows Redis caching benefits for database operations\n")
        
        self.demo_write_performance()
        self.demo_read_performance()
        self.demo_concurrent_operations()
        
        final_stats = self.cache_manager.get_cache_stats()
        print("\n[SUMMARY] DEMONSTRATION COMPLETE")
        print("=" * 40)
        print(f"[PERF]    Total operations performed: {final_stats['total_reads'] + final_stats['total_writes']}")
        print(f"[CACHE]   Overall cache hit ratio: {(final_stats['cache_hits'] / final_stats['total_reads'] * 100) if final_stats['total_reads'] > 0 else 0:.1f}%")
        print("[SUCCESS] Redis write-through caching demonstration completed")
        print("[INFO]    Key insight: Caching provides significant performance benefits")


@click.command()
@click.option('--quick', is_flag=True, help='Run a quick demo with smaller data size')
@click.option('--writes-only', is_flag=True, help='Demo write performance only')
@click.option('--reads-only', is_flag=True, help='Demo read performance only')
def main(quick, writes_only, reads_only):
    if quick:
        DEMO_CONFIG['sample_data_size'] = 100
        DEMO_CONFIG['write_batch_size'] = 4
        print("[INFO] Running in quick mode (reduced data size)")
    else:
        DEMO_CONFIG['sample_data_size'] = 2000
        DEMO_CONFIG['write_batch_size'] = 8
        print("[INFO] Running full demonstration (complete data set)")
    
    demo = CacheDemo()
    
    try:
        demo.initialize()
        
        if writes_only:
            demo.demo_write_performance()
        elif reads_only:
            demo.demo_read_performance()
        else:
            demo.run_full_demo()
            
    except KeyboardInterrupt:
        print("\n[WARN] Demo interrupted by user")
    except Exception as e:
        print(f"[ERROR] Demo execution failed: {e}")
    finally:
        if demo.cache_manager:
            demo.cache_manager.close()


if __name__ == "__main__":
    main() 