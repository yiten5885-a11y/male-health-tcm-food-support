# 安装、升级、卸载与数据重建

本页用于维护 Skill 包，不用于回答男性健康资料问题。所有命令均从项目根目录运行。

## 安装与校验

```bash
uv run python tools/manage_global_skill.py install
uv run python tools/manage_global_skill.py verify
```

安装目标固定为 `$CODEX_HOME/skills/male-health-reference`；未设置 `CODEX_HOME` 时使用当前用户的 `.codex/skills/male-health-reference`。安装器先在同一目录生成完整暂存副本、逐文件校验，再原子替换目标。

## 升级与回滚副本

```bash
uv run python tools/manage_global_skill.py upgrade
uv run python tools/manage_global_skill.py verify
```

升级前会把现有目录移动到 `$CODEX_HOME/skill-archives/male-health-reference/backup-*`，不会静默删除旧版本。备份不得放在 `$CODEX_HOME/skills` 内，否则宿主可能把备份再次发现为同名Skill。校验失败时不得把升级写成成功。

## 可恢复卸载

```bash
uv run python tools/manage_global_skill.py uninstall \
  --confirm-skill-name male-health-reference
```

卸载把当前目录移动到 `$CODEX_HOME/skill-archives/male-health-reference/removed-*`，不直接递归删除。归档目录位于Skill发现根目录之外；确认新会话不再发现Skill且不需要恢复后，才由用户自行处置该保留目录。

## 全量数据重建

```bash
uv run python tools/build_s01_full_records.py
uv run python tools/build_s02_full_records.py
uv run python tools/build_full_records.py
uv run python tools/package_skill_assets.py
uv run python tools/evaluate_full_skill.py
uv run python tools/run_acceptance_specs.py
uv run python -m unittest discover -s tests -p 'test_*.py'
```

重建后运行结构校验：

```bash
python3 /Users/yitenhua/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  skills/male-health-reference
```

数据重建和本地校验不能替代独立人工复核或真实宿主E2E。原始PDF哈希、记录数量、未知字段和审核等级必须保持守恒；若有差异，先查明原因，不得直接覆盖既有模型核对或人工核对证据。
