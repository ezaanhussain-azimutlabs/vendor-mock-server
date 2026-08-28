# Mashreq vendor mock

A dependency-free local HTTP mock for the external Mashreq APIs called by `ssk-mashreq`.
It is **not** a replacement for the `ssk-mashreq` gRPC service.

See **[API_REFERENCE.md](API_REFERENCE.md)** for the full request/response
contract of every endpoint and the gRPC → HTTP mapping.

## Start

From the repository root:

```powershell
python server.py
```

The default server is:

```text
http://localhost:8088/mashreqtest/pakistan
```

### Build and run as a Docker image

From the repository root:

```powershell
docker build -t mashreq-vendor-mock:local .
docker run --rm --name mashreq-vendor-mock -p 8088:8088 mashreq-vendor-mock:local
```

The image is self-contained and uses only the Python standard library. Override settings when starting it:

```powershell
docker run --rm -p 8088:8088 `
  -e MOCK_SCENARIO=success `
  -e MOCK_REQUIRE_AUTH=true `
  mashreq-vendor-mock:local
```

Health check:

```powershell
curl http://127.0.0.1:8088/health
```

Configuration:

```text
MOCK_PORT=8088
MOCK_BASE_PATH=/mashreqtest/pakistan
MOCK_SCENARIO=success
MOCK_REQUIRE_AUTH=true
MOCK_DELAY_MS=0
```

The mock accepts an optional port argument:

```powershell
python server.py 8088
```

Health check:

```powershell
curl http://127.0.0.1:8088/health
```

Run the successful vendor API smoke test while the server is running in another terminal:

```powershell
python smoke_test.py
```

The smoke test uses `127.0.0.1` to avoid local hostname/proxy resolution issues. You can pass another base URL explicitly:

```powershell
python smoke_test.py http://127.0.0.1:8088/mashreqtest/pakistan
```

## Pointing `ssk-mashreq` at the mock

`ssk-mashreq` loads each upstream URL from commons `ApiParam` rows. For local testing, change only the local URL values so they point to this server, for example:

```text
http://localhost:8088/mashreqtest/pakistan/oauth-v6/oauth2/token
http://localhost:8088/mashreqtest/pakistan/v1/customersearchnewpkapi/customer-search-extended
http://localhost:8088/mashreqtest/pakistan/v1/accountsummarypkapi/accounts
http://localhost:8088/mashreqtest/pakistan/v1/account-details
http://localhost:8088/mashreqtest/pakistan/v1/retailteller-transaction
```

Do not change production API parameter rows. Use a local database/configuration or a test-only override.

## Implemented routes

- `POST /oauth-v6/oauth2/token`
- `POST /v1/customersearchnewpkapi/customer-search-extended`
- `GET` and `POST /v1/accountsummarypkapi/accounts/{cif}`
- `GET` and `POST /v1/account-details/{account}`
- `POST /covbiometricverification/v1/API/BVS-Details`
- `POST /omw/wavetecfircosoftscreeningpk/v1/wavetec-screening-pk`
- `POST /wavetecpaymentsorchestratorpkapi/v1/wavetec/title-fetch`
- `POST /v1/retailteller-transaction`
- `POST /wavetecpaymentsorchestratorpkapi/v1/wavetec/fund-transfer`
- `POST /notificationhub/v1/generated/notification/emails`

The route prefix `/mashreqtest/pakistan` is configurable. Account summary/details support both methods because the current Java adapter uses GET while some captured vendor traffic describes POST.

## Scenarios

The default is successful vendor behavior. Set a global scenario:

```powershell
$env:MOCK_SCENARIO = 'success'
python server.py
```

Or select a scenario per request with `X-Mock-Scenario`:

```powershell
curl -H "X-Mock-Scenario: customer-not-found" `
  -H "Authorization: Bearer mock-core-token" `
  http://localhost:8088/mashreqtest/pakistan/v1/customersearchnewpkapi/customer-search-extended
```

Supported scenarios include:

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
invalid-gl
ibft-failure
email-failure
slow
timeout
```

The mock issues its own fake tokens. Non-token routes require a token issued by this mock and enforce the expected scope:

- `CORE`: customer, account, and retail teller APIs
- `COVALENT`: biometric API
- `FIRCO`: screening API
- `OBP`: title fetch and fund transfer
- `ENHUB`: email API

For direct manual testing, first obtain a token:

```powershell
curl -X POST `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "client_id=local-client&client_secret=local-secret&grant_type=client_credentials&scope=CORE" `
  http://localhost:8088/mashreqtest/pakistan/oauth-v6/oauth2/token
```

Use only fake/local values. The mock contains no production fixtures or credentials and does not send email or call the real Mashreq gateway.
