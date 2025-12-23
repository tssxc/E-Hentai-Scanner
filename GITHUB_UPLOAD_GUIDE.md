# GitHub 上传和绑定指南

本指南将帮助你安全地将项目上传到 GitHub 并完成绑定。

## 📋 上传前检查清单

- [x] ✅ `.gitignore` 已配置（忽略敏感文件和临时文件）
- [x] ✅ `app/config.example.py` 已创建（配置模板）
- [x] ✅ `secrets.py.example` 已存在（Cookie 模板）
- [x] ✅ `data/.gitkeep` 已创建（保留目录结构）
- [x] ✅ `logs/.gitkeep` 已创建（保留目录结构）
- [x] ✅ `README.md` 已更新（项目说明）

## 🚀 上传步骤

### 第零步：配置 Git 用户信息（首次使用需要）

如果还没有配置 Git 用户信息，需要先配置：

```bash
git config user.name "你的名字"
git config user.email "你的邮箱"
```

或者只针对当前仓库（不添加 `--global`）：
```bash
git config user.name "你的名字"
git config user.email "你的邮箱"
```

### 第一步：检查 Git 状态

在项目根目录执行：

```bash
git status
```

确认以下文件**不会被**添加到 Git：
- ❌ `data/*.db`（数据库文件）
- ❌ `data/*.json`（如果有敏感数据）
- ❌ `logs/*.log`（日志文件）
- ❌ `secrets.py`（敏感配置）
- ❌ `app/config.py`（如果包含敏感路径信息）
- ❌ `__pycache__/`（Python 缓存）

### 第二步：初始化 Git 仓库

```bash
# 如果还没有初始化
git init

# 设置默认分支为 main
git branch -M main
```

### 第三步：添加文件到暂存区

```bash
git add .
```

**重要**: 添加后再次检查：

```bash
git status
```

确认没有敏感文件被添加。如果看到 `secrets.py` 或 `data/*.db` 被添加，请检查 `.gitignore` 配置。

### 第四步：提交更改

```bash
git commit -m "Initial commit: Refactor to MVC architecture with manage.py CLI"
```

或者使用更详细的提交信息：

```bash
git commit -m "feat: 重构项目为 MVC 架构

- 创建 app/ 包整合核心功能
- 添加 manage.py 作为统一 CLI 入口
- 实现 Controller-Service-Model 分层架构
- 更新所有工具脚本以适配新结构
- 添加完整的文档和配置示例"
```

### 第五步：在 GitHub 创建仓库

1. 访问 [GitHub](https://github.com)
2. 点击右上角的 "+" → "New repository"
3. 填写仓库信息：
   - **Repository name**: `E-Hentai-Scanner`
   - **Description**: `A Python tool for scanning local manga archives and fetching E-Hentai metadata`
   - **Visibility**: 选择 Public 或 Private
   - ⚠️ **不要**勾选 "Initialize this repository with a README"（因为我们已经有了）
4. 点击 "Create repository"

### 第六步：关联远程仓库

复制 GitHub 提供的仓库 URL（例如：`https://github.com/yourusername/E-Hentai-Scanner.git`），然后执行：

```bash
git remote add origin https://github.com/yourusername/E-Hentai-Scanner.git
```

### 第七步：推送到 GitHub

```bash
git push -u origin main
```

如果这是第一次推送，GitHub 可能会要求你输入用户名和密码（或 Personal Access Token）。

## 🔐 使用 Personal Access Token

如果使用 HTTPS 推送，GitHub 不再支持密码认证，需要使用 Personal Access Token：

1. 访问 GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 点击 "Generate new token"
3. 选择权限：至少需要 `repo` 权限
4. 生成后复制 token
5. 推送时，用户名输入你的 GitHub 用户名，密码输入 token

## ✅ 验证上传

上传完成后，访问你的 GitHub 仓库页面，确认：

- ✅ 所有代码文件都已上传
- ✅ `README.md` 正确显示
- ✅ `data/` 和 `logs/` 目录存在（但内容为空）
- ✅ `.gitignore` 文件存在
- ✅ `app/config.example.py` 存在
- ❌ `secrets.py` **不应该**出现在仓库中
- ❌ `data/*.db` **不应该**出现在仓库中

## 🛡️ 安全建议

### 如果意外上传了敏感文件

如果发现敏感文件（如 `secrets.py` 或包含真实 Cookie 的配置文件）被上传：

1. **立即删除敏感信息**：
   ```bash
   # 从 Git 历史中删除文件（但保留本地文件）
   git rm --cached secrets.py
   git commit -m "Remove sensitive file"
   git push
   ```

2. **如果文件已包含敏感数据**，需要：
   - 在 GitHub 上删除该文件
   - 重新生成所有相关的密钥/Cookie
   - 考虑使用 `git filter-branch` 或 `BFG Repo-Cleaner` 清理历史记录

### 最佳实践

- ✅ 始终使用 `.gitignore` 忽略敏感文件
- ✅ 使用 `config.example.py` 提供配置模板
- ✅ 在 README 中明确说明需要配置的文件
- ✅ 定期检查 `git status` 确认没有意外添加敏感文件

## 📝 后续维护

### 更新代码

```bash
# 查看更改
git status

# 添加更改
git add .

# 提交
git commit -m "描述你的更改"

# 推送
git push
```

### 添加新功能

1. 创建功能分支：
   ```bash
   git checkout -b feature/new-feature
   ```

2. 开发完成后：
   ```bash
   git add .
   git commit -m "feat: 添加新功能"
   git push origin feature/new-feature
   ```

3. 在 GitHub 上创建 Pull Request

## 🎉 完成！

你的项目现在已经安全地上传到 GitHub 了！

如果遇到任何问题，请检查：
- `.gitignore` 是否正确配置
- 是否有敏感文件被意外添加
- GitHub 仓库权限设置是否正确

