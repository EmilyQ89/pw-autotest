import re

from playwright.sync_api import Page


class LoginPage:
    """登录页。定位器和路径按被测系统修改。"""

    URL = "/login"
    URL_PATTERN = re.compile(re.escape(URL) + r"(?:[?#]|$)")

    def __init__(self, page: Page):
        self.page = page
        self.username_input = page.get_by_placeholder("请输入用户名")
        self.password_input = page.get_by_placeholder("请输入密码")
        self.submit_button = page.get_by_role("button", name="登录")
        self.alerts = page.get_by_role("alert")

    def open(self) -> "LoginPage":
        self.page.goto(self.URL)
        return self

    def login(self, username: str, password: str) -> None:
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.submit_button.click()
