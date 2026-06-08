# 脚本目录说明

本目录存放数据仓库建设脚本。

建议后续按层拆分：

```text
scripts
├─ bronze  # Bronze 入库和校验
├─ silver  # Silver 标准层生成
├─ gold    # Gold 模型生成
└─ meta    # 元数据和语义层生成
```

当前已有脚本暂保留在 `scripts` 根目录，后续稳定后再分层迁移。
