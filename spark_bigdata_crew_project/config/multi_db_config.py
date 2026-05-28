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

# Hive Metastore配置
HIVE_CONFIG = {
    "host": os.getenv("HIVE_HOST", "localhost"),
    "port": int(os.getenv("HIVE_PORT", 10000)),
    "user": os.getenv("HIVE_USER", "hive"),
    "password": os.getenv("HIVE_PASSWORD", ""),
    "database": os.getenv("HIVE_DATABASE", "default"),
    "auth": os.getenv("HIVE_AUTH", "NONE"),
    "kerberos_principal": os.getenv("HIVE_KERBEROS_PRINCIPAL", ""),
}

# HDFS NameNode配置
HDFS_CONFIG = {
    "namenode": os.getenv("HDFS_NAMENODE", "hdfs://localhost:8020"),
    "user": os.getenv("HDFS_USER", "hdfs"),
    "data_dir": os.getenv("HDFS_DATA_DIR", "/user/hive/warehouse"),
}

# 数据源类型映射
DB_CONFIG_MAP = {
    "hive": HIVE_CONFIG,
}
