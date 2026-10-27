# Web 自动化测试框架

通用的 pytest + pytest-playwright 脚手架，Page Object 模式，报告用 Allure 3。

当前环境地址是占位符，换成真实域名后再跑用例：

| 环境 | 地址 | 命令 |
| --- | --- | --- |
| test | `https://test.xxx.com` | `pytest --env test` |
| staging | `https://staging.xxx.com` | `pytest --env staging` |

地址写在根目录 `conftest.py` 的 `ENVIRONMENTS`。临时覆盖：`pytest --base-url https://其他地址`。

## 快速开始

需要 Python 3.10+ 和 Node.js 20+（Allure 3 基于 Node，不需要 Java）。

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
npm install

cp .env.example .env     # 填测试账号
pytest --env test        # 全部用例，结果写入 allure-results/
npm run report           # 生成报告到 allure-report/
npm run report:open      # 在浏览器中打开报告
```

## 目录结构

```
pw-autotest/
├── conftest.py          # 环境地址、全局 fixture：浏览器、账号、登录状态、已登录页面；失败附件挂到报告
├── pytest.ini           # 失败截图和 trace、Allure 结果目录、用例标记
├── pyproject.toml       # ruff 配置
├── .pre-commit-config.yaml  # 提交前自动检查
├── requirements.txt     # Python 依赖
├── package.json         # Allure 3 及报告命令
├── allurerc.mjs         # Allure 报告配置：名称、中文界面、历史趋势
├── .env.example         # 账号和环境模板，复制为 .env（.env 不提交）
├── pages/               # 页面对象，模块与 tests 相同
│   ├── auth/            # 登录、退出示例
│   └── home/            # 登录后首页示例
└── tests/
    ├── conftest.py      # 多个模块共用的测试数据 fixture
    ├── auth/
    └── home/
```

按被测系统的菜单继续加模块：`pages/<模块>/` 和 `tests/<模块>/` 成对出现。一个页面一个文件，不再建子目录。例如用户列表：`pages/user/list_page.py`、`tests/user/test_list.py`，路由 `/user/list`。跨页面场景放 `tests/e2e/`。

## 接入新系统时改哪里

1. **`conftest.py` 里的 `ENVIRONMENTS`**：test / staging 的真实地址。
2. **`.env`**：测试账号。
3. **`pages/auth/login_page.py`**：登录页路径、输入框和按钮定位器。已登录状态就是靠它在界面上登录一次得到的。
4. **`pages/` 里的其他页面**：每个页面对象上的 `URL`、定位器、文案。
5. **`tests/`**：在示例登录 / 首页上继续加模块用例。

`goto("/xxx")` 会自动拼上当前环境的 `base_url`。

## 登录状态

`auth_state` 在整次运行开始时用 `LoginPage` 走一遍界面登录，把浏览器的 cookie 和 localStorage 用 Playwright 的 `storage_state` 存成文件（放在 pytest 的临时目录，不进仓库）。`logged_in_page` 用这份文件新建上下文，所以不关心被测系统把登录态放在 cookie 还是 localStorage。

- 登录失败时，所有依赖 `logged_in_page` 的用例都会报 "测试账号登录失败"，并给出原因。失败那一刻的截图和 trace 存在 `test-results/global-login/<进程>/`（单进程是 `main`，并行是 `gw0`、`gw1` …），也附在 Allure 里该进程第一条受影响用例的「准备」步骤下。用 `--tracing off` 时只留截图，不录 trace。先查账号和登录页定位器。
- 登录态在单次运行内复用。如果系统会话有效期比一次完整运行还短，需要按有效期重新登录。
- 需要另一个账号同时在线时，在用例里用 `new_context()` 新建上下文再登录，失败截图和 trace 同样会被记录。

## 编写规范

1. **只分两层。** `pages/` 放定位器和页面动作（打开、搜索、提交），其中的 `expect` 只用来确认动作完成，例如弹窗已关闭；`tests/` 放业务步骤和对结果的断言。不再加服务层、流程层。
2. **用例放进对应模块目录。** 只在一个页面里完成的用例放模块目录；跨页面的场景放 `tests/e2e/`，并调用各模块已有的页面对象，不在 `e2e` 里重写页面。
3. **fixture 放在最近的公共位置。** 全局的放根目录 `conftest.py`；多个模块共用的测试数据放 `tests/conftest.py`；只给一个模块用的放 `tests/<模块>/conftest.py`。用例文件之间不互相 import。
4. **冒烟和回归用标记区分，不建目录、不复制用例。** 每条用例只标一个：
   - `@pytest.mark.smoke`：各模块一条短主路径（能登录、页面能打开），用来快速确认系统没挂。
   - `@pytest.mark.regression`：其余用例，包括异常提示、增删改查和端到端场景。
5. **整次运行只登录一次。** 用 `logged_in_page`，它带着已保存的登录状态，不打开页面，用例自己 `goto` 目标路由。只有测登录、登出时才用未登录的 `page` 走界面。
6. **定位器优先级：** `get_by_role`（名称稳定且唯一时）> `get_by_test_id` > `get_by_label` / `get_by_placeholder` > `get_by_text`。角色加名称不唯一、文案经常改、或只能靠样式类区分时，用 `data-testid`，见下文「data-testid 约定」。不用 XPath，不用运行时生成的动态 `id`。暂时没有 `data-testid` 的组件，把 CSS 选择器封装在页面对象里，用例里不出现。
7. **断言用 `expect(...)`，不写 `sleep`。** `expect` 和 `click`、`fill` 都会自动等待。需要等页面之外的状态时用 `wait_for_function` 等条件，不用固定时长。
8. **用例独立。** 不依赖执行顺序和其他用例留下的数据。新增、编辑、删除自己造数据（姓名等带唯一后缀），在 `finally` 里清理。

示例：

```python
import pytest
from playwright.sync_api import Page, expect

from pages.home.home_page import HomePage


@pytest.mark.smoke
def test_home_opens(logged_in_page: Page):
    page = HomePage(logged_in_page).open()
    expect(page.heading).to_be_visible()
```

## 不稳定用例

一条用例时过时不过，先查原因：等待条件不对、数据被别的用例改了、环境慢，还是被测系统真有问题。确认是用例本身不稳定、一时修不好时，标记隔离，**必须写负责人、缺陷单和到期日**：

```python
@pytest.mark.quarantine(owner="张三", issue="https://缺陷系统/123", until="2026-11-15")
@pytest.mark.regression
def test_xxx(logged_in_page: Page): ...
```

框架在收集用例时检查，以下情况整次运行直接报错，不执行任何用例：

- 少写 `owner`、`issue`、`until` 任意一项，或 `until` 既不是 `"YYYY-MM-DD"` 字符串也不是 `date` 对象。
- 已过到期日。负责人要么修好并删掉标记，要么在缺陷单里说明原因后改日期。

隔离中的用例仍会运行，结果照常进报告。Allure 里能看到负责人和缺陷单链接，终端结尾会列出所有隔离用例。合并前的门禁用 `pytest -m "not quarantine"` 跳过它们，每晚全量回归不跳过，用来确认修好了没有。

约定：

- 隔离只是临时状态，到期日一般不超过两周。
- 修复后连续多次运行都通过，再删除标记。
- 不用 `sleep`、也不要用 `--reruns` 来掩盖问题。重试只给偶发的环境抖动兜底，真正不稳定的用例走隔离标记。

## data-testid 约定

`get_by_test_id("login-submit")` 对应前端的 `data-testid="login-submit"`，这是 Playwright 的默认属性名。

**命名：** `<模块>-<元素>`，小写加连字符，表达用途而不是样式，例如 `login-username`、`login-submit`、`user-list-search`、`user-list-row`。同一页面内唯一；列表行这类重复元素用同一个值，再用 `filter(has_text=...)` 区分。

**给前端的改法（Vue + Element Plus 示例）：**

```vue
<el-input v-model="form.username" data-testid="login-username" />
<el-input v-model="form.password" type="password" data-testid="login-password" />
<el-button type="primary" data-testid="login-submit">登录</el-button>
<el-table :data="rows" data-testid="user-list-table" />
```

加完在浏览器开发者工具里确认属性落在了预期的元素上：组件库会把属性透传到组件根元素或内部的原生元素，不同组件不一样。

**推进方式：**

1. 先只覆盖测试最常碰到、又最难定位的元素：登录表单、主菜单、表格行内操作按钮、弹窗确认按钮。不要求全站补齐。
2. 测试同学提需求时直接给出元素和建议的 `data-testid` 值，前端在正常需求里顺手加上，单独排期很难推动。
3. 前端约定 `data-testid` 是对测试的接口：改名或删除要同步测试，代码评审时留意。
4. 页面对象里，拿到 `data-testid` 的元素换成 `get_by_test_id`，同时删掉原来的 CSS 选择器。

如果前端已经用了别的属性名（例如 `data-qa`），在根目录 `conftest.py` 里加一个 session 级 fixture 调用 `playwright.selectors.set_test_id_attribute("data-qa")`。

## 代码检查（ruff + pre-commit）

规则写在 `pyproject.toml`。手动跑：

```bash
ruff check --fix .
ruff format .
```

**提交前自动检查。** 项目是 git 仓库后，每人装一次钩子：

```bash
pre-commit install
```

之后每次 `git commit` 都会自动跑 `.pre-commit-config.yaml` 里的检查：ruff 检查和格式化、行尾空格、文件末尾换行、YAML / TOML 语法、合并冲突标记、大于 1 MB 的文件、私钥。有问题时提交会被拦下；能自动修的会直接改好文件，重新 `git add` 再提交即可。

对全部文件跑一遍（第一次装好后、或改了检查规则后）：

```bash
pre-commit run --all-files
```

ruff 的版本在 `requirements.txt` 和 `.pre-commit-config.yaml` 各写了一次，升级时两处一起改，否则本地手动跑和提交时跑的结果可能不一样。钩子只是第一道关，CI 里也应该再跑一次 `pre-commit run --all-files`，因为有人可能用 `git commit --no-verify` 跳过。

## 并行运行

每条用例是独立的，才能并行。不要用 `-n` 配合 `--headed` 盯着看，浏览器窗口会叠在一起。

```bash
pytest --env test -n 4 --dist loadfile
```

| 参数 | 作用 |
| --- | --- |
| `-n 4` | 开 4 个进程。UI 测试每个进程都会起一个 Chromium，并各自登录一次，别一上来就 `-n auto` |
| `--dist loadfile` | 同一个文件里的用例分给同一个进程。减少同一页面被两个进程同时改数据 |

经验：本机 4 核左右用 `-n 2` 或 `-n 4`；CI 上按机器核数和被测环境能扛住的并发来定。并发太高，登录和接口会先被打满。

每个进程有自己的浏览器和 `auth_state`。4 个进程就是 4 次界面登录。

## 失败重试

默认不重试。需要给环境抖动兜底时再打开，并且次数要少：

```bash
pytest --env test --reruns 1 --reruns-delay 1
```

可以和并行一起用：

```bash
pytest --env test -n 4 --dist loadfile --reruns 1 --reruns-delay 1
```

| 参数 | 作用 |
| --- | --- |
| `--reruns 1` | 失败后再跑 1 次，总共最多 2 次 |
| `--reruns-delay 1` | 两次之间隔 1 秒，避免马上重试仍撞上瞬时故障 |

约定：

- 本地排错不要加 `--reruns`，否则第一次失败会被盖住。
- 合并前门禁最多 `--reruns 1`。每晚回归可以同样加一次。
- 同一条用例经常靠重试才过，说明它不稳定：加上文「不稳定用例」打隔离标记，不要把 `--reruns` 加大。
- 登录失败发生在进程启动时，不属于单条用例，`--reruns` 救不了，去看 `test-results/global-login/`。

Allure 里重试过的用例会留下每次尝试的记录。第一次失败、第二次通过时，报告里仍能看到第一次的截图和 trace，附件名带「第 2 次」以便区分。

## 失败截图怎么看

并行不会把不同用例的截图混在一起。pytest-playwright 按用例名分目录；重试再加 `-retryN`。Allure 里附件挂在对应那条用例上，不会串。

磁盘上的目录：

```
test-results/
├── global-login/
│   ├── main/                 # 单进程登录失败
│   └── gw0/                  # 并行时，gw0 进程登录失败
│       ├── screenshot.png
│       └── trace.zip
├── tests-auth-test-login-py-test-login-success-chromium/
│   ├── test-failed-1.png     # 第 1 次失败
│   └── trace.zip
└── tests-auth-test-login-py-test-login-success-chromium-retry1/
    ├── test-failed-1.png     # 仅第 2 次也失败时才有这个目录
    └── trace.zip
```

排查顺序：

1. **先看 Allure。** 打开失败用例，附件里有「失败截图」和「Playwright trace」。重试过的会有「失败截图（第 2 次）」。并行时全局登录失败会带进程号，例如「全局登录失败截图（gw1）」。
2. **trace 点开即可回放。** 逐步看当时的 DOM、网络请求和操作。
3. **Allure 还没生成时，去 `test-results/`。** 目录名就是用例名；全局登录失败按进程分子目录，不会互相覆盖。
4. **不要靠对比时间戳猜是哪条用例。** 文件已经按用例和进程分开了。
5. **报告里缺附件时看终端的 warnings summary。** 附件没能挂进 Allure 时不会中断运行，但会出现「…没能附到 Allure 报告」的警告，并写明磁盘上的文件位置。

`test-results/` 下次运行 pytest 时会被清空。

## 常用命令

| 场景 | 命令 |
| --- | --- |
| test 环境全部用例 | `pytest --env test` |
| staging 环境全部用例 | `pytest --env staging` |
| 只跑冒烟 | `pytest --env test -m smoke` |
| 只跑回归 | `pytest --env test -m regression` |
| 只跑一个模块 | `pytest --env test tests/auth` |
| 只跑某条用例 | `pytest --env test -k test_login_success` |
| 看着浏览器跑 | `pytest --env test --headed --slowmo 500` |
| 临时换地址 | `pytest --base-url https://其他环境地址` |
| 合并前门禁（跳过隔离用例） | `pytest --env test -m "smoke and not quarantine"` |
| 并行 | `pytest --env test -n 4 --dist loadfile` |
| 失败后重试 1 次 | `pytest --env test --reruns 1 --reruns-delay 1` |
| 并行 + 重试 | `pytest --env test -n 4 --dist loadfile --reruns 1 --reruns-delay 1` |
| 检查代码 | `ruff check .` |
| 格式化 | `ruff format .` |

`TEST_ENV` 写在 `.env` 里时，可以省略 `--env`。`--base-url` 优先级高于 `--env`。

## 报告与失败排查

```bash
pytest --env test -m smoke
npm run report
npm run report:open
```

Allure 报告里可以看：

- 按 `tests/<模块>/<文件>` 分组的结果，以及通过率和耗时。
- 每条失败用例的报错、**失败截图**、**Playwright trace**。trace 点开即可在报告里逐步回放操作、DOM 和网络请求。并行时附件仍在各自用例下；重试过的截图会标「第 N 次」。
- 冒烟、回归标记显示为标签，可按标签筛选。
- 「环境」面板里的当前环境和 `base_url`。用 `--base-url` 换成环境表以外的地址时，环境显示为 `custom`。结果目录跟随 `--alluredir`。
- 历史趋势和不稳定用例：每次 `npm run report` 都会把本次结果追加到 `allure-history.jsonl`，保留这个文件就能看到趋势。

`allure-results/` 每次运行 pytest 都会清空重写。没有生成报告前重跑，上一次结果就没了。`test-results/` 里也有同样的失败截图和 trace，下次运行时同样会被清空。

## 在编辑器里运行

Playwright 插件只支持 TypeScript，不识别 `.py` 用例。Cursor / VS Code 用 Python 扩展的测试面板：

1. 安装 **Python** 扩展（`ms-python.python`），解释器选项目里的 `venv`。
2. 打开左侧 **测试**（烧杯图标），点刷新，在用例右侧点三角运行。
3. 在 `.vscode/settings.json` 配置运行参数，`--slowmo=500` 必须写成一项，否则数字会被丢掉：

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["--env", "test", "--headed", "--slowmo=500"]
}
```
