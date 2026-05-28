#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多数据库统一配置模块

功能：集中管理MySQL/SQLServer/Oracle/Hive四大数据源的连接参数，
      通过环境变量注入实现环境隔离。
      所有配置均可被.env文件覆盖，未设置时提供安全的默认值。
"""
import os
from dotenv import load_dotenv
load_dotenv()

# MySQL配置
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", ""),
    "charset": "utf8mb4"
}

# SQL Server配置
SQLSERVER_CONFIG = {
    "host": os.getenv("SQLSERVER_HOST", "localhost"),
    "port": int(os.getenv("SQLSERVER_PORT", 1433)),
    "user": os.getenv("SQLSERVER_USER", "sa"),
    "password": os.getenv("SQLSERVER_PASSWORD", ""),
    "database": os.getenv("SQLSERVER_DATABASE", "")
}

# Oracle配置
ORACLE_CONFIG = {
    "host": os.getenv("ORACLE_HOST", "localhost"),
    "port": int(os.getenv("ORACLE_PORT", 1521)),
    "user": os.getenv("ORACLE_USER", "system"),
    "password": os.getenv("ORACLE_PASSWORD", ""),
    "service_name": os.getenv("ORACLE_SERVICE", "ORCL")
}

# Hive配置
HIVE_CONFIG = {
    "host": os.getenv("HIVE_HOST", "localhost"),
    "port": int(os.getenv("HIVE_PORT", 10000)),
    "user": os.getenv("HIVE_USER", "hive"),
    "password": os.getenv("HIVE_PASSWORD", ""),
    "database": os.getenv("HIVE_DATABASE", "default")
}

# 数据源类型映射全局调度字典
DB_CONFIG_MAP = {
    "mysql": MYSQL_CONFIG,
    "sqlserver": SQLSERVER_CONFIG,
    "oracle": ORACLE_CONFIG,
    "hive": HIVE_CONFIG
}