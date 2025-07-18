
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 21083,
    'db': 0,
    'decode_responses': True,
    'socket_connect_timeout': 5,
    'socket_timeout': 5,
    'retry_on_timeout': True
}

SQLITE_CONFIG = {
    'database_path': 'demo_database.db',
    'timeout': 20.0,
    'check_same_thread': False
}

DEMO_CONFIG = {
    'sample_data_size': 10000,
    'batch_size': 100,
    'performance_iterations': 1000,
    'cache_ttl': 600,  # 10 min ttl, change as per need
    'write_batch_size': 50
}

ZOS_CONFIG = {
    'encoding': 'cp1047',  # ebcdic encoding for z/os, was corruping data without it 
    'line_ending': '\n',
    'install_paths': [
        '/data/zopen/usr/local/bin',  # user's sqlite location, can use a script to `grep` or `command -v` sqlite3 and then `which` for the path
        '/usr/local/bin',
        '/opt/local/bin',
        '/usr/bin'
    ]
} 