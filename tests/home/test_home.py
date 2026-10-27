import pytest
from playwright.sync_api import Page, expect

from pages.home.home_page import HomePage


@pytest.mark.smoke
def test_home_opens(logged_in_page: Page):
    home = HomePage(logged_in_page).open()

    expect(home.heading).to_be_visible()
