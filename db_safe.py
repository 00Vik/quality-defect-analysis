import re

def validate_table_name(name):
    if not isinstance(name, str):
        return False
    return re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name) is not None

def q(table: str):
    """SQL安全引用"""
    return f'"{table}"'

def is_system_table(name: str):
    return name.startswith('sqlite_')