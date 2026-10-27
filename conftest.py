import os
import warnings
from datetime import date, datetime
from pathlib import Path

import allure
import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page, expect

from pages.auth.login_page import LoginPage

load_dotenv()

ENVIRONMENTS = {
    "test": "https://test.xxx.com",
    "staging": "https://staging.xxx.com",
}
DEFAULT_ENV = "test"

ENV_LABEL_KEY = pytest.StashKey[str]()
QUARANTINE_FIELDS = ("owner", "issue", "until")
QUARANTINED_KEY = pytest.StashKey[list]()

ALLURE_ATTACHMENTS = {
    "playwright_screenshot": ("失败截图", allure.attachment_type.PNG, "png"),
    "playwright_trace": ("Playwright trace", "application/vnd.allure.playwright-trace", "zip"),
}


def _xdist_worker_id() -> str:
    return os.environ.get("PYTEST_XDIST_WORKER", "main")


def _attachment_name(base: str, *, attempt: int = 1, worker: str | None = None) -> str:
    extras = []
    if attempt > 1:
        extras.append(f"第 {attempt} 次")
    if worker and worker != "main":
        extras.append(worker)
    if not extras:
        return base
    return f"{base}（{'，'.join(extras)}）"


def _attach_to_allure(path: Path | str, name: str, attachment_type, extension: str) -> None:
    """挂不上 Allure 时不中断运行，但要发警告，文件仍留在磁盘上。"""
    try:
        allure.attach.file(path, name=name, attachment_type=attachment_type, extension=extension)
    except Exception as exc:
        warnings.warn(
            f"「{name}」没能附到 Allure 报告: {exc!r}，文件在 {path}",
            pytest.PytestWarning,
            stacklevel=2,
        )


def _parse_until(until) -> date:
    if isinstance(until, datetime):
        return until.date()
    if isinstance(until, date):
        return until
    return date.fromisoformat(until)


def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default=os.getenv("TEST_ENV", DEFAULT_ENV),
        help="运行环境: test / staging（也可用环境变量 TEST_ENV）",
    )


def pytest_configure(config):
    env = config.getoption("--env")
    if env not in ENVIRONMENTS:
        names = ", ".join(ENVIRONMENTS)
        raise pytest.UsageError(f"未知环境 {env!r}，可选: {names}")

    base_url = config.getoption("--base-url")
    if not base_url:
        config.option.base_url = ENVIRONMENTS[env]
        config.stash[ENV_LABEL_KEY] = env
    elif base_url.rstrip("/") == ENVIRONMENTS[env].rstrip("/"):
        config.stash[ENV_LABEL_KEY] = env
    else:
        config.stash[ENV_LABEL_KEY] = "custom"

    if QUARANTINED_KEY not in config.stash:
        config.stash[QUARANTINED_KEY] = []


def pytest_report_header(config):
    lines = [
        f"env: {config.stash[ENV_LABEL_KEY]}",
        f"base_url: {config.option.base_url}",
    ]
    worker = _xdist_worker_id()
    if worker != "main":
        lines.append(f"xdist_worker: {worker}")
    return lines


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    workeroutput = getattr(config, "workeroutput", None)
    if workeroutput is not None:
        workeroutput["quarantined"] = config.stash.get(QUARANTINED_KEY, [])
        return

    results_dir = getattr(config.option, "allure_report_dir", None)
    if not results_dir:
        return
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, "environment.properties"), "w", encoding="utf-8") as f:
        f.write(f"Environment={config.stash[ENV_LABEL_KEY]}\n")
        f.write(f"BaseURL={config.option.base_url}\n")


def pytest_testnodedown(node, error):
    """并行时把各 worker 的隔离用例列表汇总到主进程。"""
    if not node.workeroutput:
        return
    received = node.workeroutput.get("quarantined", [])
    existing = node.config.stash.get(QUARANTINED_KEY, [])
    seen = {row[0] for row in existing}
    for row in received:
        if row[0] not in seen:
            existing.append(row)
            seen.add(row[0])
    node.config.stash[QUARANTINED_KEY] = existing


def pytest_collection_modifyitems(config, items):
    """隔离用例必须有负责人、缺陷单和到期日，过期后不允许再运行。"""
    errors = []
    quarantined = []
    for item in items:
        mark = item.get_closest_marker("quarantine")
        if mark is None:
            continue
        missing = [field for field in QUARANTINE_FIELDS if not mark.kwargs.get(field)]
        if missing:
            errors.append(f"{item.nodeid}: quarantine 缺少 {', '.join(missing)}")
            continue
        owner, issue, until = (mark.kwargs[field] for field in QUARANTINE_FIELDS)
        try:
            deadline = _parse_until(until)
        except (TypeError, ValueError):
            errors.append(
                f"{item.nodeid}: until 要写成 'YYYY-MM-DD' 字符串或 date，当前是 {until!r}"
            )
            continue
        if deadline < date.today():
            errors.append(
                f"{item.nodeid}: 隔离已于 {deadline.isoformat()} 到期，请 {owner} 修复用例或延期"
            )
            continue
        item.add_marker(allure.label("owner", owner))
        item.add_marker(allure.issue(issue, name="不稳定用例缺陷单"))
        quarantined.append((item.nodeid, owner, deadline.isoformat(), issue))

    if errors:
        raise pytest.UsageError("隔离用例不合规:\n" + "\n".join(errors))
    config.stash[QUARANTINED_KEY] = quarantined


def pytest_terminal_summary(terminalreporter, config):
    quarantined = config.stash.get(QUARANTINED_KEY, [])
    if not quarantined:
        return
    terminalreporter.section("隔离中的用例")
    for nodeid, owner, until, issue in quarantined:
        terminalreporter.write_line(f"{nodeid}  负责人 {owner}  到期 {until}  {issue}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    report.execution_count = getattr(item, "execution_count", 1)
    if report.when != "teardown":
        return
    attempt = report.execution_count or 1
    for key, path in report.user_properties:
        if key in ALLURE_ATTACHMENTS and os.path.exists(path):
            name, attachment_type, extension = ALLURE_ATTACHMENTS[key]
            _attach_to_allure(
                path,
                _attachment_name(name, attempt=attempt),
                attachment_type,
                extension,
            )


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "locale": "zh-CN",
        "viewport": {"width": 1440, "height": 900},
    }


@pytest.fixture(scope="session")
def account() -> dict:
    username = os.getenv("TEST_USERNAME")
    password = os.getenv("TEST_PASSWORD")
    if not username or not password:
        pytest.fail("请在 .env 中配置 TEST_USERNAME 和 TEST_PASSWORD（参考 .env.example）")
    return {"username": username, "password": password}


def _save_login_failure(
    page: Page, context: BrowserContext, output_dir: Path, worker: str, tracing: bool
) -> list[Path]:
    """保存全局登录失败时的截图和 trace，并附到 Allure。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    screenshot = output_dir / "screenshot.png"
    try:
        page.screenshot(path=screenshot, full_page=True)
        saved.append(("playwright_screenshot", screenshot))
    except Exception as exc:
        warnings.warn(f"全局登录失败截图没能保存: {exc!r}", pytest.PytestWarning, stacklevel=2)
    if tracing:
        trace = output_dir / "trace.zip"
        context.tracing.stop(path=trace)
        saved.append(("playwright_trace", trace))

    for key, path in saved:
        name, attachment_type, extension = ALLURE_ATTACHMENTS[key]
        _attach_to_allure(
            path,
            _attachment_name(f"全局登录{name}", worker=worker),
            attachment_type,
            extension,
        )
    return [path for _, path in saved]


@pytest.fixture(scope="session")
def auth_state(
    browser: Browser, browser_context_args: dict, account: dict, tmp_path_factory, pytestconfig
) -> str:
    """整次运行只在界面上登录一次，保存 cookie 和 localStorage。失败时留截图和 trace。"""
    path = tmp_path_factory.mktemp("auth") / "state.json"
    worker = _xdist_worker_id()
    tracing = pytestconfig.getoption("--tracing") != "off"
    context = browser.new_context(**browser_context_args)
    if tracing:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
    try:
        page = context.new_page()
        try:
            LoginPage(page).open().login(account["username"], account["password"])
            expect(page).not_to_have_url(LoginPage.URL_PATTERN)
        except Exception as exc:
            output_dir = Path(pytestconfig.getoption("--output")) / "global-login" / worker
            files = _save_login_failure(page, context, output_dir, worker, tracing)
            reason = str(exc).splitlines()[0]
            saved = ", ".join(str(f) for f in files) or "无"
            pytest.fail(
                f"测试账号登录失败，当前页面 {page.url}\n原因: {reason}\n已保存的现场: {saved}"
            )
        if tracing:
            context.tracing.stop()
        context.storage_state(path=path)
    finally:
        context.close()
    return str(path)


@pytest.fixture
def logged_in_page(new_context, auth_state: str) -> Page:
    """带登录态的新页面，不打开任何路由。用例自己进入目标路由。"""
    return new_context(storage_state=auth_state).new_page()
