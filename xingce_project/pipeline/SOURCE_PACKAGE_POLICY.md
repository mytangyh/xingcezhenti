# 最终源码包边界

包含：生产Python源码、schema、taxonomy、复现README、前后端源文件及锁文件、测试源码。冻结内容补丁、分析输入及其哈希清单须从单独的已授权重建输入包准备，不包含在公开 Git 源码中。

排除：所有`userdata/`、`pipeline/runtime/`、任何运行数据库/响应收据、旧`releases/`、`.building-*`、测试临时数据库、`.sqlite`/`.db`运行文件、node_modules、缓存、日志、venv、密钥和本机配置。测试脚本可以保留，不能把测试产生的数据库打包。

最终内容release单独打包，只包含选定版本；其只读content.sqlite是规范题库产物，不是个人数据库。源码包不得递归包含该内容包或旧release。用户运行后个人库在独立userdata目录生成，不回写源题仓库或内容包。

同一冻结输入用两个不同版本名独立构建，然后运行：

`python -m pipeline.reproducibility releases/<构建A> releases/<构建B> --output pipeline/runtime/reproducibility.json`

比较规范JSONL、资产和其余payload字节，以及SQLite实体逻辑。manifest.version允许不同；SQLite二进制是否相同单独报告，不把逻辑同构宣传为跨SQLite版本的字节一致性。
