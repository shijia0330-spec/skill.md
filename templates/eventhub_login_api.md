---
kind: api_pytest
base_url: https://api.eventhub.rahulshettyacademy.com/api
setup: none
auth:
  type: bearer_login
  login_path: /auth/login
  username_field: email
  password_field: password
  username_env: TEST_USERNAME
  password_env: TEST_PASSWORD
  token_json_path: token
cases:
  - id: TC-EVENTHUB-F-01
    method: POST
    path: /auth/login
    no_auth: true
    json_body:
      email: __ENV__:TEST_USERNAME
      password: __ENV__:TEST_PASSWORD
    expect_status: 200
    expect_json_subset:
      success: true
      user:
        email: __ENV__:TEST_USERNAME
    expect_json_schema:
      type: object
      properties:
        success:
          type: boolean
        token:
          type: string
        user:
          type: object
          properties:
            id:
              type: integer
            email:
              type: string
          required: [id, email]
      required: [success, token, user]

  - id: TC-EVENTHUB-F-02
    method: GET
    path: /auth/me
    expect_status: 200
    expect_json_subset:
      success: true
      user:
        email: __ENV__:TEST_USERNAME
    expect_json_schema:
      type: object
      properties:
        success:
          type: boolean
        user:
          type: object
          properties:
            userId:
              type: integer
            email:
              type: string
          required: [userId, email]
      required: [success, user]

  - id: TC-EVENTHUB-V-08
    method: POST
    path: /auth/login
    no_auth: true
    json_body:
      email: __ENV__:TEST_USERNAME
      password: wrong_password_123
    expect_status: 400
    expect_json_subset:
      success: false
      error: Invalid email or password

  - id: TC-EVENTHUB-V-09
    method: POST
    path: /auth/login
    no_auth: true
    json_body:
      email: "eventhub_unknown_{{timestamp}}@example.com"
      password: wrong_password_123
    expect_status: 400
    expect_json_subset:
      success: false
      error: Invalid email or password

  - id: TC-EVENTHUB-V-10-MISSING-EMAIL
    method: POST
    path: /auth/login
    no_auth: true
    json_body:
      password: wrong_password_123
    expect_status: 400

  - id: TC-EVENTHUB-V-10-MISSING-PASSWORD
    method: POST
    path: /auth/login
    no_auth: true
    json_body:
      email: __ENV__:TEST_USERNAME
    expect_status: 400

  - id: TC-EVENTHUB-V-10-EMPTY-BODY
    method: POST
    path: /auth/login
    no_auth: true
    json_body: {}
    expect_status: 400

  - id: TC-EVENTHUB-V-11-EMAIL-TYPE
    method: POST
    path: /auth/login
    no_auth: true
    json_body:
      email: 12345
      password: wrong_password_123
    expect_status: 400

  - id: TC-EVENTHUB-V-11-PASSWORD-TYPE
    method: POST
    path: /auth/login
    no_auth: true
    json_body:
      email: __ENV__:TEST_USERNAME
      password: 123456
    expect_status: 400

  - id: TC-EVENTHUB-P-02
    method: GET
    path: /auth/me
    no_auth: true
    expect_status: 401
    expect_json_subset:
      success: false
      error: Unauthorized

  - id: TC-EVENTHUB-P-03
    method: GET
    path: /auth/me
    no_auth: true
    headers:
      Authorization: Bearer invalid.eventhub.token
    expect_status: 401
    expect_json_subset:
      success: false
      error: Invalid or expired token
---

# EventHub Login API Tests

Source:

- `testcase-skills/output/EventHub_login_testcases.md`
- `https://api.eventhub.rahulshettyacademy.com/api/docs/`

Coverage:

- Successful login and authenticated `/auth/me`
- Wrong password and unknown account
- Missing required fields and invalid field types
- Missing and invalid bearer tokens

The spec does not store account credentials. Set `TEST_USERNAME` to the registered EventHub email and provide `TEST_PASSWORD` through the shell environment.

```bash
export TEST_USERNAME='registered-email@example.com'
read -s "TEST_PASSWORD?Password: "
echo
export TEST_PASSWORD
export TEST_BASE_URL='https://api.eventhub.rahulshettyacademy.com/api'

./generate.sh templates/eventhub_login_api.md
./run_pytest.sh output/eventhub_login_api.py --collect-only -q
./run_pytest.sh output/eventhub_login_api.py -v
```
