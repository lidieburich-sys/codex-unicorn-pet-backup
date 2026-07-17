# Codex Pet Backup

当前备份：Codex 内置的蓝色像素机器人 **Codex**。

> 仓库名里仍保留 `unicorn`，只是为了不改变原来的 GitHub 地址；仓库内容已经替换为当前设置的宠物。

![Codex 宠物预览](source/preview.png)

## 目录

- `installed/`：可直接恢复的 `pet.json` 与 `spritesheet.webp`
- `source/`：预览、来源信息、安装脚本与重新提取脚本

## 恢复安装

运行：

```bash
./source/install.command
```

脚本会把备份安装到：

```text
~/.codex/pets/codex-current-backup/
```

然后在 Codex 的“设置 → 宠物”中刷新，选择 **Codex (Backup)**。它与备份时当前选中的内置 Codex 宠物外观一致，但使用独立的自定义宠物目录，不会覆盖应用自带资源。

## 重新提取当前应用资源

如果 Codex 更新后想重新制作快照，可运行：

```bash
node ./source/extract_current_codex_pet.mjs
```

## 快照信息

- 当前设置 ID：`codex`
- 来源：Codex/ChatGPT macOS 应用内置资源
- 应用版本：`26.715.21425`（build `5488`）
- 贴图规格：sprite version 2，`1536 × 2288` WebP

详细校验信息见 `source/asset-metadata.json`。

## 说明

旧独角兽文件已从当前版本移除，但仍可从 Git 历史恢复。本仓库只保存宠物资源与恢复脚本，不包含聊天、账号或系统缓存数据。内置 Codex 图像的权利归其原权利人所有。
