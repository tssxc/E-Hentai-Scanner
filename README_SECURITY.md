# 🔒 安全配置说明

## Cookie 配置

本项目需要 E-Hentai 账号的 Cookie 信息才能正常工作。**请勿将包含真实 Cookie 的代码提交到公共仓库！**

### 方法 1: 使用 secrets.py（推荐）

1. 复制模板文件：
   ```bash
   cp secrets.py.example secrets.py
   ```

2. 编辑 `secrets.py`，填入你的真实 Cookie 值：
   ```python
   MY_COOKIES = {
       'ipb_member_id': '你的会员ID',
       'ipb_pass_hash': '你的密码哈希',
       'igneous': '你的 igneous cookie 值',
   }
   ```

3. 确保 `secrets.py` 已添加到 `.gitignore`（已自动配置）

### 方法 2: 使用环境变量

如果不想创建 `secrets.py` 文件，可以设置以下环境变量：

- `EH_IPB_MEMBER_ID`: 会员 ID
- `EH_IPB_PASS_HASH`: 密码哈希
- `EH_IGNEOUS`: igneous cookie 值

**Windows (PowerShell):**
```powershell
$env:EH_IPB_MEMBER_ID="你的会员ID"
$env:EH_IPB_PASS_HASH="你的密码哈希"
$env:EH_IGNEOUS="你的 igneous cookie 值"
```

**Linux/Mac:**
```bash
export EH_IPB_MEMBER_ID="你的会员ID"
export EH_IPB_PASS_HASH="你的密码哈希"
export EH_IGNEOUS="你的 igneous cookie 值"
```

## 如何获取 Cookie

1. 登录 E-Hentai 网站
2. 打开浏览器开发者工具（F12）
3. 切换到 "Network" 或 "网络" 标签
4. 刷新页面，找到任意请求
5. 查看请求头中的 Cookie，找到以下值：
   - `ipb_member_id`
   - `ipb_pass_hash`
   - `igneous`

## 注意事项

- ⚠️ **不要**将 `secrets.py` 提交到 Git 仓库
- ⚠️ **不要**在公共场合分享你的 Cookie
- ⚠️ Cookie 可能会过期，需要定期更新
- ✅ `.gitignore` 已配置，会自动排除 `secrets.py`

