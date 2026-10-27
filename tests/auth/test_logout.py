import pytest
from playwright.sync_api import Page, expect

from pages.auth.account_menu import AccountMenu
from pages.auth.login_page import LoginPage
from pages.home.home_page import HomePage


@pytest.mark.regression
def test_logout(page: Page, account: dict):
    LoginPage(page).open().login(account["username"], account["password"])
    expect(page).not_to_have_url(LoginPage.URL_PATTERN)

    AccountMenu(page).logout()

    page.goto(HomePage.URL)
    expect(page).to_have_url(LoginPage.URL_PATTERN)
