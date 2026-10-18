"""
Ascentric portal scraper.

Logs in via the standard form POST, then hits the portfolio data API
endpoint with the authenticated session cookie.

The login form is parsed with BeautifulSoup so attribute ordering inside
each <input> tag doesn't matter (the previous regex implementation missed
hidden fields that had `name=` before `type="hidden"`).
"""

import os
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


LOGIN_URL    = "https://www.platformservices.co.uk/Sites/1/advantawealth/Users/Account/LogOn"
PORTFOLIO_URL = (
    "https://www.platformservices.co.uk/Sites/1/advantawealth/"
    "Dashboard/PortfolioView/GetPortfolioViewData"
    "?clientId={client_id}&antispinner=1"
)

USERNAME_FIELD = "UserName"
PASSWORD_FIELD = "Password"


def fetch_portfolio_data() -> dict[str, Any]:
    """
    Log in to the Ascentric portal and fetch the portfolio JSON.

    Returns:
        Raw API response dict (the full JSON payload including 'data' and 'result').

    Raises:
        RuntimeError: If login fails or the portfolio endpoint returns an error.
    """
    username  = os.environ["ASCENTRIC_USERNAME"]
    password  = os.environ["ASCENTRIC_PASSWORD"]
    client_id = os.environ["ASCENTRIC_CLIENT_ID"]

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux aarch64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    # Step 1: GET the login page, parse the login form
    login_page = session.get(LOGIN_URL, timeout=30)
    login_page.raise_for_status()

    form_action, form_data = _parse_login_form(login_page.text)
    form_data[USERNAME_FIELD] = username
    form_data[PASSWORD_FIELD] = password

    post_url = urljoin(login_page.url, form_action) if form_action else LOGIN_URL

    # Step 2: POST credentials to the form's action URL
    login_response = session.post(
        post_url,
        data=form_data,
        allow_redirects=True,
        timeout=30,
    )
    login_response.raise_for_status()

    # A redirect back to /LogOn means credentials were rejected
    if "LogOn" in login_response.url or "login" in login_response.url.lower():
        raise RuntimeError(
            f"Login failed -- redirected to {login_response.url}. "
            "Check ASCENTRIC_USERNAME / ASCENTRIC_PASSWORD env vars."
        )

    # Step 3: Fetch portfolio data
    portfolio_url = PORTFOLIO_URL.format(client_id=client_id)
    session.headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.platformservices.co.uk/Sites/1/advantawealth/Dashboard",
    })

    data_response = session.get(portfolio_url, timeout=30)
    data_response.raise_for_status()

    payload = data_response.json()

    if payload.get("result") != "success":
        raise RuntimeError(f"Portfolio API returned non-success: {payload}")

    return payload


def _parse_login_form(html: str) -> tuple[str | None, dict[str, str]]:
    """
    Locate the login <form> by finding the UserName input and walking up to
    its parent form. Return (action_url, {name: value}) covering every named
    input in the form — including hidden CSRF / antiforgery tokens — so the
    POST mirrors what a browser would submit.

    Falls back to the first <form> on the page if the UserName input isn't
    found (so the error surfaces later as a login-failure rather than here).
    """
    soup = BeautifulSoup(html, "html.parser")

    anchor = soup.find("input", attrs={"name": USERNAME_FIELD})
    form = anchor.find_parent("form") if anchor else soup.find("form")
    if form is None:
        raise RuntimeError("Could not locate login form on the Ascentric login page.")

    data: dict[str, str] = {}
    for tag in form.find_all(["input", "select", "textarea"]):
        name = tag.get("name")
        if not name:
            continue
        # Skip unselected radio/checkbox; keep selected ones.
        if tag.get("type") in {"radio", "checkbox"} and not tag.has_attr("checked"):
            continue
        data[name] = tag.get("value", "")

    return form.get("action"), data
