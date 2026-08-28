# Mashreq Vendor Mock — API Reference

This mock emulates the **HTTP** APIs that `ssk-mashreq` calls on behalf of a
Mashreq vendor/ATM/CDM flow. It does **not** implement the gRPC service; it sits
behind it.

```
gRPC client  →  ssk-mashreq (gRPC :9067)  →  HTTP mock (server.py :8088)
```

All vendor HTTP paths share the prefix `/mashreqtest/pakistan`.

---

## 1. Run & verify

```bash
# terminal 1 — mock (VS Code)
python server.py            # http://127.0.0.1:8088

# terminal 2 — vendor (IntelliJ, gRPC :9067)
# run ssk-mashreq

# terminal 3 — fire the full flow
bash ~/run_full_flow.sh
```

Health check (no auth, no base path):

```bash
curl http://127.0.0.1:8088/health
```

Configuration env vars: `MOCK_PORT` (default 8088), `MOCK_REQUIRE_AUTH`
(default true), `MOCK_SCENARIO` (default success), `MOCK_DELAY_MS` (default 0).

---

## 2. Authentication

Every endpoint except `/health` and the token endpoint requires an
`Authorization: Bearer <token>` header. Tokens are issued by the mock itself.
A token is bound to one scope; using the wrong scope returns `403`.

Request an access token first:

| Path | Method | Scope |
|---|---|---|
| `/mashreqtest/pakistan/oauth-v6/oauth2/token` | POST | — |
| `/mashreqtest/pakistan/v1/oauth-v6/oauth2/token` | POST | — (used by safe-watch/SMS/email) |

### Token — request (form-urlencoded)

| Field | Example | Notes |
|---|---|---|
| `client_id` | `668d61d35ae250d460fb207c78a0de9b` | accepted, embedded in token |
| `client_secret` | `b92aff5d38fbc8e13945882a46febe4e` | accepted, not validated |
| `grant_type` | `client_credentials` | must equal `client_credentials` |
| `scope` | `CORE` / `COVALENT` / `FIRCO` / `OBP` / `ENHUB` | validated against known scopes |

### Token — response

```json
{
  "token_type": "Bearer",
  "access_token": "mock-core-668d61d3-000001",
  "scope": "CORE",
  "expires_in": 86490,
  "consented_on": 1787867138
}
```

| Field | Type | Notes |
|---|---|---|
| `token_type` | string | always `Bearer` |
| `access_token` | string | `mock-<scope>-<client_id[:8]>-<counter>` |
| `scope` | string | echo of requested scope |
| `expires_in` | int | seconds, 86490 |
| `consented_on` | int | epoch seconds |

---

## 3. Scopes

| Scope | Endpoints |
|---|---|
| `CORE` | customer search, account summary, account details, retail teller |
| `COVALENT` | biometric (BVS) |
| `FIRCO` | safe-watch screening |
| `OBP` | title fetch, fund transfer |
| `ENHUB` | email notification |

---

## 4. Scenarios

Every endpoint supports test scenarios via header `X-Mock-Scenario: <name>` or
`?scenario=<name>` on the URL, or globally via `MOCK_SCENARIO`.

| Scenario | Effect |
|---|---|
| `success` (default) | normal successful response |
| `customer-not-found` | customer search returns empty lists |
| `dedupe-error` | customer search returns `700` + `ST-WARN-001` (No Dedupe Customer Found) |
| `account-summary-error` | account summary returns HTTP 500 |
| `account-closed` | account details returns `txnStat: C`, `accStat: CLSD` |
| `account-blocked` | account details returns `isBlocked: Y` |
| `account-details-error` | account details returns HTTP 500 |
| `biometric-failure` | BVS returns `responseCode: 101` |
| `screening-violation` | screening returns `VIOLATIONFOUND` |
| `title-400` / `title-500` | title fetch returns HTTP 400 / 500 |
| `teller-failure` | retail teller returns HTTP 400 |
| `ibft-failure` | fund transfer returns HTTP 400 |
| `email-failure` | email returns `validation_error` |
| `slow` / `timeout` | adds 2s / 30s delay |

---

## 5. HTTP endpoints

### 5.1 Customer search — extended

| Method | Path | Scope |
|---|---|---|
| POST | `/mashreqtest/pakistan/v1/customersearchnewpkapi/customer-search-extended` | CORE |

**Request (JSON body)**

| Field | Example | Notes |
|---|---|---|
| `uniqueIdVal` | `"4250101403842"` | CNIC used to derive CIF/account |

**Response (200, success)**

| Field | Type | Notes |
|---|---|---|
| `dedupeDetails[]` | array | includes `cifId`, `shortName`, `fullName`, `firstName`, `lastName`, `dateOfBirth`, `nationality`, `mobileNumber`, `nationalId`, `customerName`, `customerSegment`, `branchCode`, `email` |
| `main.customerNo` | string | CIF |
| `main.customerName1` | string | customer name |
| `main.mobileNumber` | string | customer mobile |
| `main.outputList[]` | array | list of `Customer` objects |

`main.outputList[].Customer` fields: `addressline3`, `branchCode`, `customerName1`,
`dedupeCust` (CIF), `emailId`, `fullName`, `firstName`, `lastName`,
`mobileNumber`, `nationality`, `recordStat`, `shortName`, `dob`,
`accList[{accNo, brn}]`.

**Alternate responses**

- `customer-not-found`: `{"dedupeDetails":[],"main":{"outputList":[]}}`
- `dedupe-error`: `errorCode:"700"`, `errorDesc:"Host Error"`,
  `additionalDetails:[{customCode:"ST-WARN-001", customDesc:"No Dedupe Customer Found"}]`

---

### 5.2 Account summary

| Method | Path | Scope |
|---|---|---|
| GET / POST | `/mashreqtest/pakistan/v1/accountsummarypkapi/accounts/{cif}` | CORE |

**Request**

Path parameter `{cif}` (CIF from customer search). No body for GET.

**Response (200)**

```json
{
  "customerName": "MOCK CUSTOMER",
  "accounts": [{
    "accountNo": "ACCOUNT-...",
    "cifId": "CIF-...",
    "accountShortName": "MOCK CUSTOMER",
    "customerName": "MOCK CUSTOMER",
    "accountCurrency": "PKR",
    "status": "ACTIVE",
    "accType": "NEOSAV",
    "schmType": "SA",
    "availableBalance": 100000.00,
    "currentBal": 100000.00,
    "totalOverdraft": 0,
    "accountBranch": "001",
    "operatingInstruction": "S",
    "showAccount": null,
    "accountOpenDate": "2025-01-01",
    "noDebit": "N",
    "noCredit": "N"
  }],
  "loans": [], "fixedDeposits": [], "contracts": [], "trades": []
}
```

---

### 5.3 Account details

| Method | Path | Scope |
|---|---|---|
| GET / POST | `/mashreqtest/pakistan/v1/account-details/{account}` | CORE |

**Request**

Path parameter `{account}` (account number). No body for GET.

**Response (200)**

| Field | Type | Notes |
|---|---|---|
| `branch` | string | `001` |
| `accountNo` | string | echo |
| `cifId` | string | derived CIF |
| `accCls` | string | `NEOSAV` |
| `accountCurrency` | string | `PKR` |
| `customerName` | string | `MOCK CUSTOMER` |
| `accountDescription` | string | `Mock Savings Account` |
| `accountTypeDescription` | string | `Savings Account` |
| `accountClsType` | string | `S` |
| `noOfDebits` / `noOfCredits` | string | `N` |
| `isDormant` | string | `N` |
| `isBlocked` | string | `Y`/`N` |
| `postingAllowed` | string | `Y` |
| `ibanAccountNumber` | string | `PK00MOCK...` |
| `accStat` | string | `NORM`/`CLSD` |
| `txnStat` | string | `O`/`C` |
| `authStatus` | string | `A` |
| `custType` | string | `I` |
| `amountDates` | object | `acyCurrBalance`, `acyAvlBal`, `lcyCurrBalance` |
| `fieldsList`, `statusesCstmrList`, `compliance`, `jointHolders` | array | `[]` |

---

### 5.4 Biometric verification (NADRA BVS)

| Method | Path | Scope |
|---|---|---|
| POST | `/mashreqtest/pakistan/covbiometricverification/v1/API/BVS-Details` | COVALENT |

**Request (JSON body)**

| Field | Example | Notes |
|---|---|---|
| `citizenNumber` | `"4250101403842"` | CNIC (echoed back as `cnic`) |
| `mobileNumber` | `"03333333333"` | |
| `templateType` | `"WSQ"` | |
| `areaName` | location | |
| `latitude` / `longitude` | strings | |
| `IMEI` | `""` | |
| `fingerprints[]` | array | `[{index:"0", template:"<fp>"}]` |

**Response (200)**

| Field | Type | Notes |
|---|---|---|
| `responseCode` | string | `100` success / `101` failure |
| `responseDescription` | string | `Success` / failure text |
| `cnic` | string | echo of `citizenNumber` |
| `name` | string | `MOCK CUSTOMER` |
| `fatherHusbandName` | string | `MOCK PARENT` |
| `dateOfBirth` | string | `01-01-1990` |
| `presentAddress` / `permanentAddress` | string | `Mock Address` |
| `city` / `province` / `district` | string | `Karachi` / `Sindh` |

---

### 5.5 Safe-watch screening (Firco)

| Method | Path | Scope |
|---|---|---|
| POST | `/mashreqtest/pakistan/omw/wavetecfircosoftscreeningpk/v1/wavetec-screening-pk` | FIRCO |

**Request (JSON body)**

| Field | Example | Notes |
|---|---|---|
| `paymentID` | `"WAV..."` | echoed as `transactionId` |
| `name` | `"Zain Abbas"` | |
| `senderIDType` | `"CNIC"` | |
| `cnic` | `"4250101403842"` | |
| `dateOfBirth` | `"01-01-1993"` | |
| `valueDate` | `"2026-08-18"` | |

**Response (200)**

```json
{
  "fircoScreeningStatusCode": "000",
  "fircoScreeningStatus": "NOVIOLATIONFOUND",
  "transactionId": "WAV..."
}
```

`fircoScreeningStatus` is `NOVIOLATIONFOUND` by default, `VIOLATIONFOUND` under
`screening-violation`.

---

### 5.6 IBFT title fetch

| Method | Path | Scope |
|---|---|---|
| POST | `/mashreqtest/pakistan/wavetecpaymentsorchestratorpkapi/v1/wavetec/title-fetch` | OBP |

**Request (JSON body)**

| Field | Example |
|---|---|
| `receiverInfo.accountNumber` | `"MOCK-BENEFICIARY"` |
| `receiverInfo.bankIMD` | `"627197"` |

**Response (200)**

```json
{
  "internalRefId": "MOCK-INTERNAL-REF-1001",
  "correlationId": "MOCK-CORRELATION-1001",
  "unifiedTitleFetchStatus": true,
  "accountInfo": {
    "title": "MOCK BENEFICIARY",
    "accountNumber": "MOCK-BENEFICIARY",
    "beneficiaryIban": "PK00MOCK0000000000000000",
    "destinationPaymentSystem": "02"
  },
  "participantInfo": {"receiverBankIMD": "627197"}
}
```

---

### 5.7 Retail teller transaction

| Method | Path | Scope |
|---|---|---|
| POST | `/mashreqtest/pakistan/v1/retailteller-transaction` | CORE |

Used by `cashDeposit` and `cashWithdrawal`.

**Request (JSON body)**

| Field | Example | Notes |
|---|---|---|
| `transactionAccountNo` | `"MOCK-ACCOUNT"` | |
| `transactionBranch` / `postingBranch` | `"001"` | |
| `transactionAmount` | `100` | |
| `transactionCurrency` | `"PKR"` | |
| `productId` | `"CDPO"` | |
| `offsetBranch` | `"001"` | |
| `offsetAccountNo` | `"MOCK-OFFSET"` | |
| `offsetCurrency` | `"PKR"` | |
| `valueDate` | date | |

**Response (200)**

| Field | Type | Notes |
|---|---|---|
| `status` | string | `Success` |
| `transactionRefNo` / `referance` | string | `001-MOCK-000001` |
| `msgId` / `trackingId` | string | `MOCK-MSG-...` / `MOCK-TRACKING-...` |
| `product`, `branch`, `txnBranch`, `txnAccount`, `txnCurrency`, `txnAmount`, `offsetBranch`, `offsetAccount`, `offsetCurrency`, `offsetAmount` | string | echoes of request |
| `authStat` / `recStat` | string | `A` |
| `chargeDetails` | array | `[]` |

---

### 5.8 IBFT fund transfer

| Method | Path | Scope |
|---|---|---|
| POST | `/mashreqtest/pakistan/wavetecpaymentsorchestratorpkapi/v1/wavetec/fund-transfer` | OBP |

**Request (JSON body)**

| Field | Example |
|---|---|
| `senderInfo.accountNumber` | `"MOCK-SENDER"` |
| `receiverInfo.accountNumber` | `"MOCK-BENEFICIARY"` |
| `amount` | `"1000"` |

**Response (200)**

```json
{
  "txnrefno": "MOCK-IBFT-000001",
  "paymentTransferStatus": "SUCCESS",
  "responseStatus": {"customCode": "0000", "customDesc": "Success"}
}
```

---

### 5.9 Email notification

| Method | Path | Scope |
|---|---|---|
| POST | `/mashreqtest/pakistan/notificationhub/v1/generated/notification/emails` | ENHUB |

**Request (JSON body)**

| Field | Example |
|---|---|
| `source` | `"MOCK-SOURCE"` |
| `email[]` | `[{messageId, to, subject, body}]` |

**Response (200)**

```json
{
  "status": "success",
  "data": {"email": [{
    "status": "success",
    "statusDescription": "Accepted by mock notification hub",
    "statusRef": "MOCK-EMAIL-1001",
    "messageId": "MOCK-MESSAGE"
  }]}
}
```

---

## 6. gRPC → HTTP mapping

| gRPC RPC | HTTP calls made by ssk-mashreq | Mock covered |
|---|---|---|
| `accountInquiry` | token(CORE) → customer-search → account-summary (if customer found) | ✅ |
| `nadraBiometric` (walk-in) | token(COVALENT) → BVS-Details → token(FIRCO) → screening | ✅ |
| `nadraBiometric` (non-walk-in) | token(COVALENT) → BVS-Details | ✅ |
| `titleFetch` | token(CORE) → account-details | ✅ |
| `ibftTitleFetch` | token(OBP) → title-fetch | ✅ |
| `cashDeposit` | token(CORE) → retail-teller | ✅ |
| `cashWithdrawal` | token(CORE) → retail-teller | ✅ |
| `doIbft` | token(OBP) → fund-transfer | ✅ |
| `chequeDeposit` | ticket API (CHEQUE_DEPOSIT URL) | ❌ not implemented |
| `genericService` (BANK_LIST) | none (DB `cms_*` tables) | ✅ n/a |
| `genericService` (SEND_EMAIL) | email notification | ✅ |
| SMS send | push-sms (`/v1/push-sms`) | ❌ not implemented |

---

## 7. Files

| File | Purpose |
|---|---|
| `server.py` | HTTP mock (stdlib only) |
| `smoke_test.py` | direct HTTP smoke test against the mock |
| `API_ENDPOINTS.md` | flow overview + curl examples |
| `API_REFERENCE.md` | this document |
