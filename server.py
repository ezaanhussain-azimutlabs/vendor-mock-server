#!/usr/bin/env python3
"""Local Mashreq vendor HTTP mock.

This server intentionally uses only the Python standard library so it can be
started without installing dependencies. It emulates the HTTP APIs called by
ssk-mashreq; it does not implement the ssk-mashreq gRPC service.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


DEFAULT_PORT = int(os.getenv("MOCK_PORT", "8088"))
REQUIRE_AUTH = os.getenv("MOCK_REQUIRE_AUTH", "false").lower() not in {"0", "false", "no"}
DEFAULT_SCENARIO = os.getenv("MOCK_SCENARIO", "success")

TOKENS: dict[str, str] = {}
TOKEN_COUNTER = 0
TRANSACTION_COUNTER = 0


def json_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def stable_id(value: str, prefix: str, length: int = 10) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest().upper()
    return f"{prefix}-{digest[:length]}"


def fake_cif(identifier: str) -> str:
    return stable_id(identifier or "default", "CIF", 9)


def fake_account(identifier: str) -> str:
    return stable_id(identifier or "default", "ACCOUNT", 12)


def scenario_from(handler: BaseHTTPRequestHandler) -> str:
    explicit = handler.headers.get("X-Mock-Scenario")
    if explicit:
        return explicit.strip().lower()
    query = parse_qs(urlparse(handler.path).query)
    return query.get("scenario", [DEFAULT_SCENARIO])[0].strip().lower()


def should_fail(scenario: str, *names: str) -> bool:
    return scenario in {name.lower() for name in names}


class MockHandler(BaseHTTPRequestHandler):
    server_version = "MashreqVendorMock/1.0"

    def log_message(self, format: str, *args: object) -> None:
        # Do not print request bodies, headers, tokens, or personal data.
        sys.stdout.write("[vendor-mock] " + (format % args) + "\n")
        sys.stdout.flush()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        if path == "/health":
            self._send(200, {"status": "UP", "service": "mashreq-vendor-mock"})
            return
        if self._is_account_summary(path):
            if not self._authorized("CORE"):
                return
            self._account_summary(path, scenario_from(self))
            return
        if self._is_account_details(path):
            if not self._authorized("CORE"):
                return
            self._account_details(path, scenario_from(self))
            return
        self._send(404, {"error": "mock route not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        # print(path)
        scenario = scenario_from(self)
        # print(scenario)

        if path in {
            "/mashreqtest/pakistan/oauth-v6/oauth2/token",
            "/mashreqtest/pakistan/v1/oauth-v6/oauth2/token",
        }:
            self._token()
            return

        if self._is_account_summary(path):
            if not self._authorized("CORE"):
                return
            self._account_summary(path, scenario)
            return
        if self._is_account_details(path):
            if not self._authorized("CORE"):
                return
            self._account_details(path, scenario)
            return

        required_scope = self._required_scope(path)
        if not self._authorized(required_scope):
            return

        if path == "/mashreqtest/pakistan/v1/customersearchnewpkapi/customer-search-extended":
            self._customer_search(scenario)
        elif path == "/mashreqtest/pakistan/covbiometricverification/v1/API/BVS-Details":
            self._biometric(scenario)
        elif path == "/mashreqtest/pakistan/omw/wavetecfircosoftscreeningpk/v1/wavetec-screening-pk":
            self._screening(scenario)
        elif path == "/mashreqtest/pakistan/wavetecpaymentsorchestratorpkapi/v1/wavetec/title-fetch":
            self._title_fetch(scenario)
        elif path == "/mashreqtest/pakistan/v1/retailteller-transaction":
            self._retail_teller(scenario)
        elif path == "/mashreqtest/pakistan/wavetecpaymentsorchestratorpkapi/v1/wavetec/fund-transfer":
            self._fund_transfer(scenario)
        elif path == "/mashreqtest/pakistan/notificationhub/v1/generated/notification/emails":
            self._email(scenario)
        else:
            self._send(404, {"error": "mock route not found", "path": path})

    @staticmethod
    def _is_account_summary(path: str) -> bool:
        return path.startswith("/mashreqtest/pakistan/v1/accountsummarypkapi/accounts/")

    @staticmethod
    def _is_account_details(path: str) -> bool:
        return path.startswith("/mashreqtest/pakistan/v1/account-details/")

    @staticmethod
    def _required_scope(path: str) -> str | None:
        if path == "/mashreqtest/pakistan/covbiometricverification/v1/API/BVS-Details":
            return "COVALENT"
        if path == "/mashreqtest/pakistan/omw/wavetecfircosoftscreeningpk/v1/wavetec-screening-pk":
            return "FIRCO"
        if path in {
            "/mashreqtest/pakistan/wavetecpaymentsorchestratorpkapi/v1/wavetec/title-fetch",
            "/mashreqtest/pakistan/wavetecpaymentsorchestratorpkapi/v1/wavetec/fund-transfer",
        }:
            return "OBP"
        if path == "/mashreqtest/pakistan/notificationhub/v1/generated/notification/emails":
            return "ENHUB"
        return "CORE"

    def _read_body(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > 10 * 1024 * 1024:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        content_type = self.headers.get("Content-Type", "")
        # print(content_type)
        if "application/x-www-form-urlencoded" in content_type:
            return {key: values[-1] for key, values in parse_qs(raw.decode("utf-8")).items()}

        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def _token(self) -> None:
        global TOKEN_COUNTER
        try:
            body = self._read_body()
        except ValueError as exc:
            self._send(400, {"error": "invalid_request", "error_description": str(exc)})
            return
        if not isinstance(body, dict) or body.get("grant_type", "client_credentials") != "client_credentials":
            self._send(400, {"error": "unsupported_grant_type"})
            return

        scope = str(body.get("scope") or "CORE").upper()
        if scope not in {"CORE", "COVALENT", "FIRCO", "OBP", "ENHUB"}:
            self._send(400, {"error": "invalid_scope", "scope": scope})
            return

        # Accept the client credentials from the request (client_secret is
        # parsed but not used by the mock). Keep the token deterministic and
        # traceable so smoke tests stay reproducible.
        client_id = str(body.get("client_id") or "local-client")
        TOKEN_COUNTER += 1
        token = f"mock-{scope.lower()}-{client_id[:8]}-{TOKEN_COUNTER:06d}"
        TOKENS[token] = scope

        self._send(200, {
            "token_type": "Bearer",
            "access_token": token,
            "scope": scope,
            "expires_in": 86490,
            "consented_on": int(time.time()),
        })

    def _authorized(self, expected_scope: str | None = None) -> bool:
        if not REQUIRE_AUTH:
            return True
        header = self.headers.get("Authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        actual_scope = TOKENS.get(token)
        if actual_scope is None:
            self._send(401, {"error": "invalid_token", "error_description": "Use a token issued by this mock"})
            return False
        if expected_scope and actual_scope != expected_scope:
            self._send(403, {"error": "insufficient_scope", "required_scope": expected_scope})
            return False
        return True

    def _delay(self, scenario: str) -> None:
        configured = os.getenv("MOCK_DELAY_MS")
        milliseconds = int(configured) if configured and configured.isdigit() else 0
        if scenario in {"slow", "delay"}:
            milliseconds = max(milliseconds, 2000)
        if scenario in {"timeout", "timed-out"}:
            milliseconds = max(milliseconds, 30000)
        if milliseconds:
            time.sleep(milliseconds / 1000)

    def _customer_search(self, scenario: str) -> None:
        self._delay(scenario)
        try:
            body = self._read_body()
        except ValueError:
            self._send(400, {"errorCode": "400", "errorDesc": "Invalid request"})
            return
        identifier = ""
        if isinstance(body, dict):
            identifier = str(body.get("uniqueIdVal") or body.get("UniqueIdVal") or "mock-customer")
        if should_fail(scenario, "customer-not-found", "no-data", "not-found"):
            self._send(200, {
                "dedupeDetails": [],
                "main": {"outputList": []},
            })
            return
        if should_fail(scenario, "dedupe-error"):
            self._send(200, {
                "errorResponse": {
                    "statusCode": "204",
                    "statusReason": "No data found",
                    "errorCode": "700",
                    "additionalDetails": [],
                },
                "errorCode": "700",
                "errorDesc": "Host Error",
                "additionalDetails": [{
                    "customCode": "ST-WARN-001",
                    "customDesc": "No Dedupe Customer Found",
                }],
                "main": {"outputList": []},
            })
            return
        cif = fake_cif(identifier)
        account = fake_account(identifier)
        customer = {
            "addressline3": "Mock Address",
            "branchCode": "001",
            "customerName1": "MOCK CUSTOMER",
            "dedupeCust": cif,
            "emailId": "mock.customer@example.test",
            "fullName": "MOCK CUSTOMER",
            "firstName": "MOCK",
            "lastName": "CUSTOMER",
            "mobileNumber": "03000000000",
            "nationality": "PK",
            "recordStat": "O",
            "shortName": "MOCK CUSTOMER",
            "dob": "1990-01-01",
            "accList": [{"accNo": account, "brn": "001"}],
        }
        # Include both the current adapter shape and the log-observed shape.
        self._send(200, {
            "dedupeDetails": [{
                "cifId": cif,
                "shortName": "MOCK CUSTOMER",
                "fullName": "MOCK CUSTOMER",
                "firstName": "MOCK",
                "lastName": "CUSTOMER",
                "dateOfBirth": "1990-01-01",
                "nationality": "PK",
                "mobileNumber": "03000000000",
                "nationalId": identifier or "MOCK-CNIC",
                "customerName": "MOCK CUSTOMER",
                "customerSegment": "MOCK",
                "branchCode": "001",
                "email": "mock.customer@example.test",
            }],
            "main": {
                "customerNo": cif,
                "customerName1": "MOCK CUSTOMER",
                "mobileNumber": "03000000000",
                "outputList": [customer],
            },
        })

    def _account_summary(self, path: str, scenario: str) -> None:
        self._delay(scenario)
        if should_fail(scenario, "account-summary-error", "upstream-500"):
            self._send(500, {"errorCode": "500", "errorDesc": "Mock account summary failure"})
            return
        cif = path.rsplit("/", 1)[-1]
        account = fake_account(cif)
        customer = "MOCK CUSTOMER"
        self._send(200, {
            "customerName": customer,
            "accounts": [{
                "accountNo": account,
                "cifId": cif,
                "accountShortName": customer,
                "customerName": customer,
                "accountCurrency": "PKR",
                "status": "ACTIVE",
                "accType": "NEOSAV",
                "schmType": "SA",
                "availableBalance": 100000.00,
                "currentBal": 100000.00,
                "totalOverdraft": 0,
                "accountBranch": "001",
                "operatingInstruction": "S",
                "showAccount": None,
                "accountOpenDate": "2025-01-01",
                "noDebit": "N",
                "noCredit": "N",
            }],
            "loans": [], "fixedDeposits": [], "contracts": [], "trades": [],
        })

    def _account_details(self, path: str, scenario: str) -> None:
        self._delay(scenario)
        if should_fail(scenario, "account-closed", "closed-account"):
            txn_stat, acc_stat = "C", "CLSD"
        elif should_fail(scenario, "account-blocked", "blocked-account"):
            txn_stat, acc_stat = "O", "NORM"
        else:
            txn_stat, acc_stat = "O", "NORM"
        if should_fail(scenario, "account-details-error", "upstream-500"):
            self._send(500, {"errorCode": "500", "errorDesc": "Mock account details failure"})
            return
        account = path.rsplit("/", 1)[-1]
        self._send(200, {
            "acStatCbDormant": "N",
            "branch": "001",
            "accountNo": account,
            "cifId": fake_cif(account),
            "accCls": "NEOSAV",
            "accountCurrency": "PKR",
            "customerName": "MOCK CUSTOMER",
            "accountDescription": "Mock Savings Account",
            "accountTypeDescription": "Savings Account",
            "accountClsType": "S",
            "noOfDebits": "N",
            "noOfCredits": "N",
            "isDormant": "N",
            "isBlocked": "Y" if should_fail(scenario, "account-blocked", "blocked-account") else "N",
            "postingAllowed": "Y",
            "ibanAccountNumber": "PK00MOCK0000000000000000",
            "accStat": acc_stat,
            "txnStat": txn_stat,
            "authStatus": "A",
            "custType": "I",
            "amountDates": {
                "acyCurrBalance": 100000.00,
                "acyAvlBal": 100000.00,
                "lcyCurrBalance": 100000.00,
            },
            "fieldsList": [],
            "statusesCstmrList": [],
            "compliance": [],
            "jointHolders": [],
        })

    def _biometric(self, scenario: str) -> None:
        self._delay(scenario)
        if should_fail(scenario, "biometric-failure", "fingerprint-failure"):
            self._send(200, {
                "responseCode": "101",
                "responseDescription": "Fingerprint does not match",
            })
            return
        try:
            body = self._read_body()
        except ValueError:
            body = {}
        cnic = body.get("citizenNumber", "MOCK-CNIC") if isinstance(body, dict) else "MOCK-CNIC"
        self._send(200, {
            "responseCode": "100",
            "responseDescription": "Success",
            "cnic": cnic,
            "name": "MOCK CUSTOMER",
            "fatherHusbandName": "MOCK PARENT",
            "dateOfBirth": "01-01-1990",
            "presentAddress": "Mock Address",
            "permanentAddress": "Mock Address",
            "city": "Karachi",
            "province": "Sindh",
            "district": "Karachi",
        })

    def _screening(self, scenario: str) -> None:
        self._delay(scenario)
        try:
            body = self._read_body()
        except ValueError:
            body = {}
        payment_id = body.get("paymentID", "MOCK-PAYMENT-ID") if isinstance(body, dict) else "MOCK-PAYMENT-ID"
        violation = should_fail(scenario, "screening-violation", "violation")
        self._send(200, {
            "fircoScreeningStatusCode": "001" if violation else "000",
            "fircoScreeningStatus": "VIOLATIONFOUND" if violation else "NOVIOLATIONFOUND",
            "transactionId": payment_id,
        })

    def _title_fetch(self, scenario: str) -> None:
        self._delay(scenario)
        if should_fail(scenario, "title-400", "title-error"):
            self._send(400, {
                "errorCode": "400",
                "errorDesc": "Mock title fetch failed",
                "customCode": "TITLE-400",
                "customDesc": "Beneficiary account could not be resolved",
            })
            return
        if should_fail(scenario, "title-500", "upstream-500"):
            self._send(500, {"errorCode": "500", "errorDesc": "Mock gateway error"})
            return
        try:
            body = self._read_body()
        except ValueError:
            body = {}
        receiver = body.get("receiverInfo", {}) if isinstance(body, dict) else {}
        account = str(receiver.get("accountNumber") or "MOCK-BENEFICIARY")
        self._send(200, {
            "internalRefId": "MOCK-INTERNAL-REF-1001",
            "correlationId": "MOCK-CORRELATION-1001",
            "unifiedTitleFetchStatus": True,
            "accountInfo": {
                "title": "MOCK BENEFICIARY",
                "accountNumber": account,
                "beneficiaryIban": "PK00MOCK0000000000000000",
                "destinationPaymentSystem": "02",
            },
            "participantInfo": {"receiverBankIMD": "627197"},
        })

    def _retail_teller(self, scenario: str) -> None:
        self._delay(scenario)
        try:
            body = self._read_body()
        except ValueError:
            body = {}
        if should_fail(scenario, "teller-failure", "invalid-gl", "retail-teller-error"):
            self._send(400, {
                "errorCode": "INVALID_GL_ACCOUNT",
                "errorDesc": "Invalid GL or account",
                "status": "Failed",
            })
            return
        global TRANSACTION_COUNTER
        TRANSACTION_COUNTER += 1
        branch = str(body.get("transactionBranch") or body.get("postingBranch") or "001") if isinstance(body, dict) else "001"
        account = str(body.get("transactionAccountNo") or "MOCK-ACCOUNT") if isinstance(body, dict) else "MOCK-ACCOUNT"
        amount = body.get("transactionAmount", 0) if isinstance(body, dict) else 0
        reference = f"{branch}-MOCK-{TRANSACTION_COUNTER:06d}"
        self._send(200, {
            "msgId": f"MOCK-MSG-{TRANSACTION_COUNTER:06d}",
            "trackingId": f"MOCK-TRACKING-{TRANSACTION_COUNTER:06d}",
            "status": "Success",
            "transactionRefNo": reference,
            "referance": reference,
            "product": body.get("productId", "CDPO") if isinstance(body, dict) else "CDPO",
            "branch": branch,
            "txnBranch": branch,
            "txnAccount": account,
            "txnCurrency": body.get("transactionCurrency", "PKR") if isinstance(body, dict) else "PKR",
            "txnAmount": str(amount),
            "offsetBranch": body.get("offsetBranch", "001") if isinstance(body, dict) else "001",
            "offsetAccount": body.get("offsetAccountNo", "MOCK-OFFSET") if isinstance(body, dict) else "MOCK-OFFSET",
            "offsetCurrency": body.get("offsetCurrency", "PKR") if isinstance(body, dict) else "PKR",
            "offsetAmount": str(amount),
            "valueDate": body.get("valueDate") if isinstance(body, dict) else None,
            "authStat": "A",
            "recStat": "A",
            "chargeDetails": [],
        })

    def _fund_transfer(self, scenario: str) -> None:
        self._delay(scenario)
        if should_fail(scenario, "ibft-failure", "fund-transfer-error"):
            self._send(400, {
                "errorCode": "4001",
                "errorDesc": "Invalid beneficiary account",
                "responseStatus": {
                    "customCode": "4001",
                    "customDesc": "Invalid beneficiary account",
                },
            })
            return
        global TRANSACTION_COUNTER
        TRANSACTION_COUNTER += 1
        self._send(200, {
            "txnrefno": f"MOCK-IBFT-{TRANSACTION_COUNTER:06d}",
            "paymentTransferStatus": "SUCCESS",
            "responseStatus": {"customCode": "0000", "customDesc": "Success"},
        })

    def _email(self, scenario: str) -> None:
        self._delay(scenario)
        try:
            body = self._read_body()
        except ValueError:
            body = {}
        email_items = body.get("email", []) if isinstance(body, dict) else []
        message_id = "MOCK-MESSAGE"
        if isinstance(email_items, list) and email_items and isinstance(email_items[0], dict):
            message_id = str(email_items[0].get("messageId") or message_id)
        if should_fail(scenario, "email-failure", "notification-error"):
            self._send(200, {
                "status": "success",
                "data": {"email": [{
                    "status": "validation_error",
                    "statusDescription": "Mock notification failure",
                    "statusRef": "-99",
                    "messageId": message_id,
                }]},
            })
            return
        self._send(200, {
            "status": "success",
            "data": {"email": [{
                "status": "success",
                "statusDescription": "Accepted by mock notification hub",
                "statusRef": "MOCK-EMAIL-1001",
                "messageId": message_id,
            }]},
        })

    def _send(self, status: int, body: object) -> None:
        payload = json_bytes(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    server = ThreadingHTTPServer(("0.0.0.0", port), MockHandler)
    print(f"Mashreq vendor mock listening on http://localhost:{"127.0.1"}:{port}")
    print(f"Default scenario: {DEFAULT_SCENARIO}; auth required: {REQUIRE_AUTH}")
    print("Use X-Mock-Scenario or ?scenario=... for test scenarios.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Mashreq vendor mock")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
