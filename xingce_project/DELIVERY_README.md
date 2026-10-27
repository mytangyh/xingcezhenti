# 启动与数据恢复

公开 Git 版本的完整说明见 [README.md](README.md)。

与此前私人离线 ZIP 不同，Git 不包含预构建 dist、大型内容 release、个人数据、冻结重建输入、密封评分包或原交付哈希收据。先构建前端，再把已有可信内容包合并到本仓库的 xingce_project/releases，最后运行：

```sh
python xingce_project/start_workbench.py --check
python xingce_project/start_workbench.py
```

若使用私有打包工具重新导出 ZIP，须准备可信内容版本与已构建 dist，并提供单独审阅过的验收摘要；新生成收据仅对应该次 ZIP，不对应历史交付。所有个人库、QA 数据与评分密钥必须继续排除。
