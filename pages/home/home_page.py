from playwright.sync_api import Page, expect

from pages.auth.login_page import LoginPage


class HomePage:
    """登录后落地页。路径和标题按被测系统修改。"""

    URL = "/"

    def __init__(self, page: Page):
        self.page = page
        self.heading = page.get_by_role("heading").first

    def open(self) -> "HomePage":
        self.page.goto(self.URL)
        expect(self.page).not_to_have_url(LoginPage.URL_PATTERN)
        return self
