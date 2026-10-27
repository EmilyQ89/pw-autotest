import pytest
from playwright.sync_api import Page, expect

from pages.auth.login_page import LoginPage


@pytest.mark.smoke
def test_login_success(page: Page, account: dict):
    LoginPage(page).open().login(account["username"], account["password"])

    expect(page).not_to_have_url(LoginPage.URL_PATTERN)


@pytest.mark.regression
@pytest.mark.parametrize(
    "username, password, message",
    [
        ("", None, "请输入用户名"),
        (None, "", "请输入密码"),
        (None, "wrong-password", "用户名或密码错误"),
    ],
    ids=["empty_username", "empty_password", "wrong_password"],
)
def test_login_failure(page: Page, account: dict, username, password, message: str):
    """None 表示使用 .env 中的测试账号。提示文案按被测系统修改。"""
    login_page = LoginPage(page).open()
    login_page.login(
        account["username"] if username is None else username,
        account["password"] if password is None else password,
    )

    expect(login_page.alerts.filter(has_text=message)).to_be_visible()
    expect(page).to_have_url(LoginPage.URL_PATTERN)
