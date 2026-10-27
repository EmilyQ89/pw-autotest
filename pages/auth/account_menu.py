from playwright.sync_api import Page, expect

from pages.auth.login_page import LoginPage


class AccountMenu:
    """右上角账号菜单：退出登录。定位器按被测系统修改。"""

    def __init__(self, page: Page):
        self.page = page
        self.user_button = page.get_by_role("button", name="用户")

    def logout(self) -> None:
        self.user_button.click()
        self.page.get_by_role("menuitem", name="退出登录").click()
        dialog = self.page.get_by_role("dialog")
        dialog.get_by_role("button", name="确定").click()
        expect(self.page).to_have_url(LoginPage.URL_PATTERN)
