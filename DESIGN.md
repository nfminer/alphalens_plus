# AlphalensPlus 模组设计与工程实践参考

> 本文档记录 `alphalens_plus` 从原始状态到可发布生产模组的完整工程优化过程，涵盖目录结构、包管理、Git 工作流、CI/CD 发布流程、测试策略及安全实践。可直接作为同类 Python 科学计算/量化工具箱的模板参考。

---

## 一、设计哲学

- **对外极简**：用户只需 `import alphalens_plus as ap`，常用函数全部暴露在包顶层。
- **对内清晰**：子模块按职责分层（utils → performance → plotting → tears），避免循环依赖。
- **发布安全**：零长期凭证（Trusted Publishing），public 仓库中内部文档加密存储。
- **多平台验证**：CI 矩阵覆盖 Windows/Linux/ARM64 × Python 3.9/3.12，但发布产物唯一。

---

## 二、目录与模块划分

```
alphalens_plus/
├── __init__.py      # 版本号 + 顶层 API 统一暴露
├── utils.py         # 远期收益率、因子清洗、分箱排序、基准收益
├── performance.py   # 组合权重、换手率、IC / Mean IC
├── plotting.py      # 可视化函数（IC 时序、分组收益、累计收益等）
├── tears.py         # Tear Sheet 组装层
├── opt.py           # 最小方差组合优化（可选依赖 cvxpy）
└── _logging.py      # 内部日志配置（loguru），避免与标准库 logging 冲突

tests/
├── conftest.py      # pytest fixtures（模拟数据）
├── test_utils.py    # 核心工具函数测试
├── test_performance.py
├── test_opt.py      # cvxpy 可选，未安装时自动跳过
├── test_version.py
└── test_import.py   # 包导入与顶层 API 存在性检查

根目录配置:
├── pyproject.toml              # 包配置、依赖、pytest 配置
├── requirements.txt            # 保留参考（阿里云镜像）
├── .gitattributes              # git-crypt 加密标记
├── .git-crypt/filter.py        # 透明加密过滤器脚本
├── .github/workflows/release.yml  # CI/CD 发布流程
├── DESIGN.md                   # 本文件
├── LOGGING.md                  # 开发日志（加密存储）
└── README.md                   # 面向用户的使用文档
```

---

## 三、包管理设计

### 3.1 pyproject.toml 结构

- **`[build-system]`**：`setuptools>=61.0` + `wheel`，兼容 `uv` / `pip` / `build`。
- **`[project]`**：
  - `name` 使用 **PyPI 分发名**（如 `dsf-alphalens`）。
  - 导入名由 `[tool.setuptools] packages` 单独指定（如 `alphalens_plus`），两者解耦。
  - `classifiers` 必须放在 `[project]` 表内，不能另开 `[project.classifiers]` 子表（TOML 作用域陷阱）。
- **`[project.optional-dependencies]`**：`cvxpy` 归入 `opt` extra，未安装时不破坏包导入。
- **`[tool.pytest.ini_options]`**：原生集成 pytest 配置，无需额外 `pytest.ini`。

### 3.2 版本号管理

- 采用**双点硬编码**：`pyproject.toml` 的 `project.version` 与 `alphalens_plus/__init__.py` 的 `__version__` 保持一致。
- 发布时同时修改两处。不引入 `setuptools_scm` 或 `versioneer`，避免干净环境构建失败。

### 3.3 顶层 API 暴露

`__init__.py` 从各子模块显式导入最常用函数，并更新 `__all__`：

```python
from .utils import get_clean_factor_and_forward_returns, quantize_factor, ...
from .performance import factor_information_coefficient, ...
from .tears import create_full_tear_sheet, ...
```

`opt` 模块使用 `try/except ImportError` 包裹，避免未安装 `cvxpy` 时导致整包无法导入。

---

## 四、日志设计

- 原始文件 `logging.py` 重命名为 `_logging.py`，**彻底避免与 Python 标准库 `logging` 冲突**。
- 该模块仅供内部使用，不暴露到 `__all__`。
- 如需外部访问日志对象，可通过 `from alphalens_plus._logging import logger`（不推荐，保持私有）。

---

## 五、Git 工作流设计

### 5.1 分支策略

| 分支 | 用途 | 保护规则 |
|------|------|----------|
| `master` | 主开发分支，合并已通过验证的 PR | **Protected**，需 Pull Request |
| `release` | 触发正式发布构建 | 视团队需求决定是否保护 |
| `feature/*` | 功能开发 | 无保护，push 后提 PR |

### 5.2 Commit 规范

采用简洁的语义化前缀：
- `refactor:` 重构（版本控制、模块重命名、API 暴露）
- `ci:` CI/CD 相关（workflow 调整、构建修复）
- `chore:` 工程杂项（加密配置、文档迁移）
- `fix:` 功能修复

---

## 六、发布流程设计（GitHub Actions）

### 6.1 触发条件

```yaml
on:
  push:
    branches:
      - release
  release:
    types: [published]
```

- **日常开发 push 到 master**：不触发发布。
- **正式发布**： push 到 `release` 分支，或手动在 GitHub 上创建 Release。

### 6.2 三阶段 Job 设计

#### Stage 1: test-build（矩阵验证）

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, windows-latest, ubuntu-24.04-arm]
    python-version: ["3.9", "3.12"]
```

- 在 6 个组合上分别执行 `python -m build` + `twine check dist/*`。
- **不上传 artifact**，仅验证构建正确性。
- 纯 Python 包的平台标签为 `py3-none-any`，无需多平台分别构建 wheel。

#### Stage 2: release-build（唯一发布产物）

- 仅在 `ubuntu-latest` + Python 3.9 上构建一次。
- 产物（wheel + sdist）通过 `actions/upload-artifact@v4` 上传，artifact name 唯一（`release-dists`）。
- 依赖 `test-build` 全部成功，避免构建失败时仍尝试发布。

#### Stage 3: pypi-publish（发布到 PyPI）

```yaml
permissions:
  id-token: write
environment:
  name: pypi
```

- 使用 `actions/download-artifact@v4` 下载单一 artifact，**不使用 `merge-multiple`**，避免同名文件覆盖导致 `BadZipFile`。
- 使用 `pypa/gh-action-pypi-publish@release/v1`，**不设置 `password`**，强制走 Trusted Publishing (OIDC)。

### 6.3 关键教训

> **不要**让多个矩阵 job 同时上传同名 wheel 后再 `merge-multiple: true`。zip 文件在并发/覆盖场景下极易损坏，报错 `BadZipFile: Bad magic number for central directory`。

---

## 七、安全实践

### 7.1 Trusted Publishing（零长期凭证）

**原理**：GitHub Actions 向 GitHub OIDC 服务商申请短期 JWT（内含仓库、workflow、分支、environment 声明），PyPI 验证声明后颁发临时上传令牌（约 15 分钟有效）。

**优势**：
- 仓库内不存在任何 `PYPI_TOKEN` secret。
- 临时令牌自动过期，泄露窗口极小。
- 可精确绑定到具体仓库 + workflow + environment。

### 7.2 git-crypt 内部文档加密

**场景**：public 仓库中存放 `AGENTS.md`、`CLAUDE.md`、`LOGGING.md` 等内部设计文档，对外不可见但对协作者透明。

**实现**：
1. `.git-crypt/filter.py`：基于 `cryptography.fernet` 的对称加解密脚本。
2. `.git-crypt/key`：Fernet 密钥（`.gitignore` 排除，不进入版本库）。
3. `.gitattributes`：标记需要加密的文件。
4. Git 配置 `filter.crypt.clean/smudge`：在 `git add` 时自动加密，`git checkout` 时自动解密。

**协作者 onboarding**：
```bash
# 收到密钥文件后，放置到 .git-crypt/key
# 重新 checkout 触发 smudge 解密
git checkout -- .
```

**历史明文提醒**：git-crypt 只加密**未来**的 commit，已 push 的历史 commit 中的文件仍是明文。如需彻底隐藏，需用 `git filter-repo` 重写历史并 force push。

---

## 八、测试策略

- **框架**：pytest（替代原有的 unittest）。
- **数据**：全部使用 `numpy`/`pandas` 生成模拟数据，零外部依赖（不依赖 `jtdata`、本地 parquet、`empyrical` 等）。
- **结构**：`conftest.py` 集中管理 fixtures，`test_opt.py` 使用 `pytest.importorskip(