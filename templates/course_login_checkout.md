---
kind: ui_pytest_playwright
# Course practice shop (Rahul Shetty client). Change if your lecture uses another URL.
base_url: https://rahulshettyacademy.com
viewport:
  width: 1280
  height: 720
layer: H
priority: P0
business: course-login-checkout
steps:
  # 1. Open login
  - action: goto
    path: /client

  # 2. Login — replace email/password with the account from YOUR lecture
  - action: fill
    l1_placeholder: email@example.com
    value: "REPLACE_WITH_COURSE_EMAIL"
  - action: fill
    l1_label: "Password"
    l1_placeholder: "enter your passsword"
    value: "REPLACE_WITH_COURSE_PASSWORD"
  - action: click
    l1_role: button
    l1_name: Login

  # 3. Add one product (change the name if your lecture used another item)
  - action: click
    l1_role: button
    l1_name: "Add To Cart"
    # If several products show this button, codegen/healer may click the first.
    # After a fail, tighten this with the product title (ZARA COAT 3, etc.).

  # 4. Open cart
  - action: click
    l1_role: button
    l1_name: Cart

  # 5. Checkout
  - action: click
    l1_role: button
    l1_name: Checkout

  # 6. Country + place order (typical on this shop)
  - action: fill
    l1_placeholder: "Select Country"
    value: "India"
  - action: click
    l1_role: button
    l1_name: India
  - action: click
    l1_role: button
    l1_name: "Place Order"

expect:
  - type: visible_text
    text: "Thankyou for the order"
    exact: false
---

# Course practice: login → add product → checkout

You own the **steps and the assert**. Locators (`l1_*`) are what AI / codegen may fix when the run is red.

## You fill in

| Field | Where |
|-------|--------|
| Email / password | `REPLACE_WITH_COURSE_*` above — use the lecture account |
| Product | If the first "Add To Cart" is wrong, tell Cursor the product name |
| Success text | Keep `Thankyou for the order` unless your page says something else |

## Generate and run (from skills pack root)

```bash
./generate.sh templates/course_login_checkout.md
./run_pytest.sh output/course_login_checkout.py --headed -v
```

If `run_pytest.sh` is missing UI extras:

```bash
python3 -m pytest output/course_login_checkout.py --headed -v
```
