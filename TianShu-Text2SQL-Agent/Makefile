# TianShu Text2SQL Agent — Makefile
# 在 Git Bash (Windows) 或 Linux/macOS 终端中使用
# 所有目标均可从项目根目录执行

.PHONY: install test lint harness api closure baseline verify clean env help web-smoke

# ── 默认目标 ──
help:
	@echo "TianShu Text2SQL Agent — 可用目标:"
	@echo ""
	@echo "  make install   安装全部依赖（含 API 和开发工具）"
	@echo "  make lint      运行 Ruff 代码检查"
	@echo "  make test      运行全部单元测试"
	@echo "  make harness   运行 12 项 Harness 安全检查"
	@echo "  make api       启动 REST API 服务（需设置 TIANSHU_LOCAL_API_TOKEN）"
	@echo "  make closure   运行本地 API 安全闭环验收"
	@echo "  make baseline  生成发布基线快照"
	@echo "  make verify    一键验收：编译 → 测试 → 安全 → 闭环"
	@echo "  make clean     清理临时文件和缓存"
	@echo "  make env       检查环境配置状态"
	@echo "  make web-smoke 运行 Web UI Smoke 验收"
	@echo ""

# ── 安装依赖 ──
install:
	pip install -e ".[api,dev]"

# ── 运行 Ruff 代码检查 ──
lint:
	python -m ruff check .

# ── 运行全部单元测试 ──
test:
	python -m pytest -q

# ── 运行 12 项 Harness 安全检查 ──
harness:
	python harness/run_harness.py

# ── 启动 REST API 服务 ──
api:
	python scripts/run_api.py --config config/api_config.yml

# ── 本地 API 安全闭环验收（8 项验证） ──
closure:
	python scripts/run_local_api_closure.py \
		--api-config config/api_config.yml \
		--tianshu-config config/tianshu_target.yml

# ── 生成发布基线快照（Source 模式，无 LLM 调用） ──
baseline:
	python harness/run_baseline_freeze.py

# ── 一键验收：编译 → 测试 → 安全 → 闭环 ──
verify:
	@echo "═══════════════════════════════════════════════════════"
	@echo "  TianShu Text2SQL Agent v$$(python -c \"from src.version import VERSION; print(VERSION)\") — 完整验收流水线"
	@echo "═══════════════════════════════════════════════════════"
	@echo ""
	@echo "[1/5] Ruff 代码检查..."
	@python -m ruff check . && echo "  ✅ Ruff 通过" || (echo "  ❌ Ruff 失败" && exit 1)
	@echo ""
	@echo "[2/5] 代码编译检查..."
	@python -m compileall -q src harness tests && echo "  ✅ 编译通过" || (echo "  ❌ 编译失败" && exit 1)
	@echo ""
	@echo "[3/5] 全部单元测试..."
	@python -m pytest -q && echo "  ✅ 测试通过" || (echo "  ❌ 测试失败" && exit 1)
	@echo ""
	@echo "[4/5] 12 项 Harness 安全检查..."
	@python harness/run_harness.py && echo "  ✅ Harness 通过" || (echo "  ❌ Harness 失败" && exit 1)
	@echo ""
	@echo "[5/5] 本地 API 安全闭环..."
	@python scripts/run_local_api_closure.py \
		--api-config config/api_config.yml \
		--tianshu-config config/tianshu_target.yml && echo "  ✅ 闭环通过" || (echo "  ❌ 闭环失败" && exit 1)
	@echo ""
	@echo "═══════════════════════════════════════════════════════"
	@echo "  ✅ 验收完成"
	@echo "═══════════════════════════════════════════════════════"

# ── 清理临时文件 ──
clean:
	@echo "清理 __pycache__ 目录..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "清理 .pytest_cache 目录..."
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "清理 .ruff_cache 目录..."
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "清理 harness 临时报告..."
	@rm -rf harness/reports/test_tmp 2>/dev/null || true
	@echo "✅ 清理完成"

# ── 检查环境配置状态 ──
env:
	@echo "═══════════════════════════════════════════════════════"
	@echo "  环境配置检查"
	@echo "═══════════════════════════════════════════════════════"
	@echo ""
	@echo "Python 版本:"
	@python --version 2>&1 || echo "  ❌ Python 不可用"
	@echo ""
	@echo "pip 可用性:"
	@pip --version 2>&1 || echo "  ❌ pip 不可用"
	@echo ""
	@echo "TIANSHU_LOCAL_API_TOKEN:"
	@if [ -n "$$TIANSHU_LOCAL_API_TOKEN" ]; then \
		echo "  ✅ 已设置 ($$(echo $$TIANSHU_LOCAL_API_TOKEN | wc -c) 字符)"; \
	else \
		echo "  ⚠️ 未设置（本地安全模式需要，至少 32 字符）"; \
	fi
	@echo ""
	@echo "PYTHONIOENCODING:"
	@if [ -n "$$PYTHONIOENCODING" ]; then \
		echo "  $$PYTHONIOENCODING"; \
	else \
		echo "  ⚠️ 未设置（Windows 建议设为 utf-8）"; \
	fi
	@echo ""
	@echo "DuckDB 数据库:"
	@if [ -f "../TianShu/data/tianShu.duckdb" ]; then \
		echo "  ✅ ../TianShu/data/tianShu.duckdb 存在"; \
	else \
		echo "  ⚠️ 未找到 DuckDB 文件（检查 config/tianshu_target.yml）"; \
	fi
	@echo ""
	@echo "契约目录:"
	@if [ -d "../TianShu/contracts" ]; then \
		echo "  ✅ ../TianShu/contracts 存在"; \
	else \
		echo "  ⚠️ 未找到契约目录"; \
	fi
	@echo ""

# ── Web UI Smoke 验收（Phase 7）──
web-smoke:
	python scripts/run_web_ui_smoke.py \n		--api-config config/api_config.yml \n		--tianshu-config config/tianshu_target.yml
