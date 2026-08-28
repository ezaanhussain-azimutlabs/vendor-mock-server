#!/usr/bin/env python3
"""Smoke-test the running Mashreq vendor mock.

Usage:
    python smoke_test.py
    python smoke_test.py http://localhost:8088/mashreqtest/pakistan
"""

from __future__ import annotations

import http.client
import json
import sys
import urllib.parse


BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088/mashreqtest/pakistan").rstrip("/")
ROOT = urllib.parse.urlparse(BASE).scheme + "://" + urllib.parse.urlparse(BASE).netloc


def call(method: str, path: str, body=None, headers=None, base: str = BASE):
    headers = dict(headers or {})
    data = None
    if body is not None:
        if headers.get("Content-Type") == "application/x-www-form-urlencoded":
            data = urllib.parse.urlencode(body).encode()
        else:
            headers.setdefault("Content-Type", "application/json")
            data = json.dumps(body).encode()
    parsed = urllib.parse.urlparse(base + path)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=5)
    try:
        connection.request(method, parsed.path + (f"?{parsed.query}" if parsed.query else ""), body=data, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        return response.status, json.loads(payload)
    finally:
        connection.close()


def token(scope: str) -> str:
    status, response = call(
        "POST",
        "/oauth-v6/oauth2/token",
        {"client_id": "local-client", "client_secret": "local-secret", "grant_type": "client_credentials", "scope": scope},
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert status == 200 and response["scope"] == scope
    return response["access_token"]


def headers(access_token: str):
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def main():
    status, health = call("GET", "/health", base=ROOT)
    assert status == 200 and health["status"] == "UP"

    core = headers(token("CORE"))
    status, customer = call("POST", "/v1/customersearchnewpkapi/customer-search-extended", {"uniqueIdVal": "mock-customer"}, core)
    assert status == 200 and customer["main"]["outputList"]
    cif = customer["main"]["outputList"][0]["dedupeCust"]

    status, summary = call("GET", f"/v1/accountsummarypkapi/accounts/{cif}", headers=core)
    assert status == 200 and summary["accounts"]
    account = summary["accounts"][0]["accountNo"]

    status, details = call("GET", f"/v1/account-details/{account}", headers=core)
    assert status == 200 and details["txnStat"] == "O"

    status, teller = call("POST", "/v1/retailteller-transaction", {"transactionAccountNo": account, "transactionAmount": 100}, core)
    assert status == 200 and teller["status"] == "Success" and teller["transactionRefNo"]

    bvs = headers(token("COVALENT"))
    status, response = call("POST", "/covbiometricverification/v1/API/BVS-Details", {}, bvs)
    assert status == 200 and response["responseCode"] == "100"

    firco = headers(token("FIRCO"))
    status, response = call("POST", "/omw/wavetecfircosoftscreeningpk/v1/wavetec-screening-pk", {"paymentID": "MOCK-PAYMENT"}, firco)
    assert status == 200 and response["fircoScreeningStatus"] == "NOVIOLATIONFOUND"

    obp = headers(token("OBP"))
    status, response = call("POST", "/wavetecpaymentsorchestratorpkapi/v1/wavetec/title-fetch", {"receiverInfo": {"accountNumber": "MOCK-BENEFICIARY"}}, obp)
    assert status == 200 and response["unifiedTitleFetchStatus"] is True
    status, response = call("POST", "/wavetecpaymentsorchestratorpkapi/v1/wavetec/fund-transfer", {}, obp)
    assert status == 200 and response["responseStatus"]["customCode"] == "0000"

    enhub = headers(token("ENHUB"))
    status, response = call("POST", "/notificationhub/v1/generated/notification/emails", {"email": [{"messageId": "MOCK-MESSAGE"}]}, enhub)
    assert status == 200 and response["status"] == "success"

    print("Mashreq vendor mock smoke test: PASS")
    print(f"Base URL: {BASE}")
    print(f"Fixture CIF: {cif}")
    print(f"Fixture account: {account}")


if __name__ == "__main__":
    main()
