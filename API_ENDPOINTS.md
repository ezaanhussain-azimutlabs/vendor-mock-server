# Mashreq API endpoints

This file lists both sides of the local test flow:

```text
Client/middleware -> ssk-mashreq gRPC -> Mashreq vendor mock HTTP
```

Use only fake/local values. The mock does not call the real Mashreq gateway.

## 1. Mashreq vendor mock HTTP APIs

Default base URL:

```text
http://127.0.0.1:8088/mashreqtest/pakistan
```

Health does not use the base path:

```text
GET http://127.0.0.1:8088/health
```

All other APIs require a Bearer token issued by the mock unless `MOCK_REQUIRE_AUTH=false`.

| Method | Endpoint | Scope | Successful response marker |
|---|---|---|---|
| POST | `/oauth-v6/oauth2/token` | None | `access_token` |
| POST | `/v1/customersearchnewpkapi/customer-search-extended` | CORE | `main.outputList` |
| GET/POST | `/v1/accountsummarypkapi/accounts/{cif}` | CORE | `accounts` |
| GET/POST | `/v1/account-details/{accountNumber}` | CORE | `txnStat: O` |
| POST | `/covbiometricverification/v1/API/BVS-Details` | COVALENT | `responseCode: 100` |
| POST | `/omw/wavetecfircosoftscreeningpk/v1/wavetec-screening-pk` | FIRCO | `fircoScreeningStatus: NOVIOLATIONFOUND` |
| POST | `/wavetecpaymentsorchestratorpkapi/v1/wavetec/title-fetch` | OBP | `unifiedTitleFetchStatus: true` |
| POST | `/v1/retailteller-transaction` | CORE | `status: Success` |
| POST | `/wavetecpaymentsorchestratorpkapi/v1/wavetec/fund-transfer` | OBP | `responseStatus.customCode: 0000` |
| POST | `/notificationhub/v1/generated/notification/emails` | ENHUB | `status: success` |

### Obtain a token

```powershell
$BASE="http://127.0.0.1:8088/mashreqtest/pakistan"

$TOKEN=(curl.exe -sS -X POST "$BASE/oauth-v6/oauth2/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "client_id=local-client&client_secret=local-secret&grant_type=client_credentials&scope=CORE" | ConvertFrom-Json).access_token
```

Use it on CORE APIs:

```powershell
curl.exe -sS -X POST "$BASE/v1/customersearchnewpkapi/customer-search-extended" `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  --data '{"uniqueIdVal":"MOCK-CUSTOMER"}'
```

## Complete curl test script

Run the following commands in PowerShell while `server.py` is running. These commands call every vendor mock endpoint.

### Health

```powershell
curl.exe -sS "http://127.0.0.1:8088/health"
```

### Create tokens for every scope

```powershell
curl.exe -sS -X POST "http://127.0.0.1:8088/mashreqtest/pakistan/oauth-v6/oauth2/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "grant_type=client_credentials&scope=CORE" 

$COVALENT_TOKEN=(curl.exe -sS -X POST "$BASE/oauth-v6/oauth2/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "grant_type=client_credentials&scope=COVALENT" | ConvertFrom-Json).access_token

$FIRCO_TOKEN=(curl.exe -sS -X POST "$BASE/oauth-v6/oauth2/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "grant_type=client_credentials&scope=FIRCO" | ConvertFrom-Json).access_token

$OBP_TOKEN=(curl.exe -sS -X POST "$BASE/oauth-v6/oauth2/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "grant_type=client_credentials&scope=OBP" | ConvertFrom-Json).access_token

$ENHUB_TOKEN=(curl.exe -sS -X POST "$BASE/oauth-v6/oauth2/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "grant_type=client_credentials&scope=ENHUB" | ConvertFrom-Json).access_token
```

### Customer search

```powershell
curl.exe -sS -X POST "http://127.0.0.1:8088/mashreqtest/pakistan/v1/customersearchnewpkapi/customer-search-extended" `
  -H "Authorization: Bearer $CORE_TOKEN" `
  -H "Content-Type: application/json" `
  --data '{"uniqueIdVal":"MOCK-CUSTOMER"}'


```

### Account summary - GET

```powershell
curl.exe -sS -X GET "$BASE/v1/accountsummarypkapi/accounts/$CIF" `
  -H "Authorization: Bearer $CORE_TOKEN"
CIF-225B86EBC

```

### Account summary - POST

```powershell
curl.exe -sS -X POST "$BASE/v1/accountsummarypkapi/accounts/$CIF" `
  -H "Authorization: Bearer $CORE_TOKEN"
```

### Account details - GET

```powershell
curl.exe -sS -X GET "$http://127.0.0.1:8088/mashreqtest/pakistan/v1/account-details/$ACCOUNT" `
  -H "Authorization: Bearer $CORE_TOKEN"
  ACCOUNT-225B86EBC5ED
  mock-core-000001
```

### Account details - POST

```powershell
curl.exe -sS -X POST "$BASE/v1/account-details/$ACCOUNT" `
  -H "Authorization: Bearer $CORE_TOKEN"
```

### Biometric verification

```powershell
curl.exe -sS -X POST "$BASE/covbiometricverification/v1/API/BVS-Details" `
  -H "Authorization: Bearer $COVALENT_TOKEN" `
  -H "Content-Type: application/json" `
  --data '{
    "citizenNumber":"MOCK-CNIC",
    "fingerIndex":"1",
    "fingerTemplate":"MOCK-FINGERPRINT"
  }'
```

### Firco screening

```powershell
curl.exe -sS -X POST "$BASE/omw/wavetecfircosoftscreeningpk/v1/wavetec-screening-pk" `
  -H "Authorization: Bearer $FIRCO_TOKEN" `
  -H "Content-Type: application/json" `
  --data '{
    "paymentID":"MOCK-PAYMENT-ID",
    "senderName":"MOCK CUSTOMER",
    "senderCNIC":"MOCK-CNIC",
    "amount":"1000"
  }'
```

### IBFT title fetch

```powershell
curl.exe -sS -X POST "$BASE/wavetecpaymentsorchestratorpkapi/v1/wavetec/title-fetch" `
  -H "Authorization: Bearer $OBP_TOKEN" `
  -H "Content-Type: application/json" `
  --data '{
    "receiverInfo": {
      "accountNumber":"MOCK-BENEFICIARY",
      "bankIMD":"627197"
    }
  }'
```

### Retail teller transaction

```powershell
curl.exe -sS -X POST "$BASE/v1/retailteller-transaction" `
  -H "Authorization: Bearer $CORE_TOKEN" `
  -H "Content-Type: application/json" `
  --data '{
    "transactionAccountNo":"MOCK-ACCOUNT",
    "transactionBranch":"001",
    "transactionAmount":100,
    "transactionCurrency":"PKR",
    "productId":"CDPO"
  }'
```

### IBFT fund transfer

```powershell
curl.exe -sS -X POST "$BASE/wavetecpaymentsorchestratorpkapi/v1/wavetec/fund-transfer" `
  -H "Authorization: Bearer $OBP_TOKEN" `
  -H "Content-Type: application/json" `
  --data '{
    "senderInfo":{"accountNumber":"MOCK-SENDER"},
    "receiverInfo":{"accountNumber":"MOCK-BENEFICIARY"},
    "amount":"1000"
  }'
```

### Email notification

```powershell
curl.exe -sS -X POST "$BASE/notificationhub/v1/generated/notification/emails" `
  -H "Authorization: Bearer $ENHUB_TOKEN" `
  -H "Content-Type: application/json" `
  --data '{
    "source":"MOCK-SOURCE",
    "email":[{
      "messageId":"MOCK-MESSAGE-ID",
      "to":"mock.customer@example.test",
      "subject":"Mock notification",
      "body":"This is a local mock email."
    }]
  }'
```

### Call an error scenario

```powershell
curl.exe -sS -X POST "$BASE/v1/customersearchnewpkapi/customer-search-extended" `
  -H "Authorization: Bearer $CORE_TOKEN" `
  -H "X-Mock-Scenario: customer-not-found" `
  -H "Content-Type: application/json" `
  --data '{"uniqueIdVal":"MOCK-CUSTOMER"}'
```

### Scope mapping

| API type | Token scope |
|---|---|
| Customer, account, teller | CORE |
| Biometric | COVALENT |
| Firco screening | FIRCO |
| Title fetch, fund transfer | OBP |
| Email | ENHUB |

### Test scenarios

Set globally before starting the mock:

```powershell
$env:MOCK_SCENARIO="screening-violation"
python server.py
```

Or send a request header:

```text
X-Mock-Scenario: customer-not-found
```

Supported examples:

```text
customer-not-found
no-data
dedupe-error
account-closed
account-blocked
biometric-failure
screening-violation
title-400
title-500
teller-failure
ibft-failure
email-failure
slow
timeout
```

## 2. ssk-mashreq gRPC APIs

The application listens on:

```text
127.0.0.1:9067
```

Proto files:

```text
ssk-mashreq/src/main/proto/VendorProcessing.proto
ssk-mashreq/src/main/proto/Commons.proto
```

Service name:

```text
vendor.VendorProcessingService
```

| RPC method | Request | Response |
|---|---|---|
| `accountInquiry` | `AccountInquiryRequest` | `AccountInquiryResponse` |
| `nadraBiometric` | `NadraBiometricRequest` | `NadraBiometricResponse` |
| `titleFetch` | `TitleFetchRequest` | `TitleFetchResponse` |
| `cashDeposit` | `CashDepositRequest` | `CashDepositResponse` |
| `genericService` | `GenericRequest` | `GenericResponse` |
| `ibftTitleFetch` | `IbftTitleFetchRequest` | `IbftTitleFetchResponse` |
| `doIbft` | `IbftRequest` | `IbftResponse` |
| `cashWithdrawal` | `CashWithdrawalRequest` | `CashWithdrawalResponse` |
| `chequeDeposit` | `ChequeDepositRequest` | `ChequeDepositResponse` |

Example gRPC call:

```powershell
grpcurl.exe -plaintext `
  -import-path "C:\Users\ezaan.hussain_azimut\ssk-mashreq\src\main\proto" `
  -proto VendorProcessing.proto `
  -proto Commons.proto `
  -d '{
    "meta": {
      "transactionId": "EXISTING_TRANSACTION_ID",
      "deviceId": "TEST-DEVICE",
      "action": "CASH_DEPOSIT"
    },
    "cnic": "MOCK-CNIC",
    "mobileNumber": "03000000000"
  }' `
  127.0.0.1:9067 `
  vendor.VendorProcessingService/accountInquiry
```

The transaction ID must already exist in the configured `ssk_mashreq` database.

## 3. Application HTTP and metrics ports

| Port | Purpose | URL |
|---:|---|---|
| 9071 | Spring Boot health/API port | `http://127.0.0.1:9071/check/health` |
| 9067 | gRPC service | `127.0.0.1:9067` |
| 9068 | Metrics port | Configured metrics endpoint |

The HTTP port is not a replacement for the gRPC vendor service. Vendor HTTP calls are made by `ssk-mashreq` to the mock server on port 8088.




























<!-- oauth req : -->
Form-UrlEncoded POST to:https://internal-apigateway-pk.mashreqdev.com/mashreqtest/pakistan/oauth-v6/oauth2/token | Fields: {client_id=668d61d35ae250d460fb207c78a0de9b, client_secret=b92aff5d38fbc8e13945882a46febe4e, scope=CORE, grant_type=client_credentials} 

<!-- res: -->
Status: 200 | Body: {"token_type":"Bearer","access_token":"AAIgNjY4ZDYxZDM1YWUyNTBkNDYwZmIyMDdjNzhhMGRlOWKVl-Q-UDljPRtce7j9es4ryF-o775j1R-47UavJ6zUYitWWfykPd46yOR58tIXeAfxW1MxBZjuRXd4YuwA4xHLGI-4sanP0CEOWP9_j6vyK09ufVQ-4zWKTXsepHesr5w","scope":"CORE","expires_in":86490,"consented_on":1787044324} | Success : true 





<!-- customer-search-extended -->

JSON POST to: https://internal-apigateway-pk.mashreqdev.com/mashreqtest/pakistan/v1/customersearchnewpkapi/customer-search-extended | Payload: {"uniqueIdVal":"4250101403842"} 

