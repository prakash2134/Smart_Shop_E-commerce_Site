# Smartshop: FastAPI (customers) + Django (admin), prices in INR

Both apps share one SQLite database. Django owns the schema and migrations, and FastAPI reads and writes the same tables.

Ports used: storefront 5500, API 8010, Django admin 8001. If one is busy, `run_all.py` tells you which.

## Setup (once)
1. Install Python 3.10 or newer.
2. Open a terminal in this folder (the one with `manage.py`).
3. Create and activate a virtual environment:
   - Mac/Linux: `python3 -m venv venv && source venv/bin/activate`
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
4. `pip install -r requirements.txt`
5. `python setup_project.py`
   This creates `.env`, the migrations, the database, sample products and the admin user (admin / admin123), and writes `database.sql`.

## Run
`python run_all.py` starts everything and opens the storefront. Press Ctrl+C to stop.
- Storefront: http://localhost:5500
- API docs: http://localhost:8010/docs
- Admin dashboard: http://localhost:8001/dashboard/ (admin / admin123), data admin at /admin/

## Try it
1. Click Log in, then "Create an account". Add products, open Cart, press "Pay with Stripe". Demo mode confirms instantly and sends an alert (the email prints in the terminal).
2. "Simulate a failed payment" shows the payment-failure alert.
3. Open the admin at http://localhost:8001/admin/ > Orders and change an order's status. The storefront shows the alert within about 2 seconds, with no refresh. Open the storefront in two tabs to see cart changes sync live.
4. Open the dashboard for sales, revenue trend, top sellers and low-stock alerts. Export CSV or PDF.
5. Roles: in /admin/ > Users tick "Staff status" (staff) or "Superuser status" (admin). Staff and admin users see an Admin button in the storefront, and only they can call `/admin/orders`.
6. Product images: add them in /admin/ > Products. They show in the storefront.

## Real Stripe payments (INR)
1. In `.env` set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`, then restart `run_all.py`.
2. Forward webhooks: `stripe listen --forward-to localhost:8010/payments/webhook`
3. Pay with test card 4242 4242 4242 4242. Your Stripe account must support INR.

## Real email
Fill the `SMTP_*` values in `.env` (a Gmail app password works).

## Google and Facebook login (Auth0)
1. In Auth0 create a Single Page Application. Add `http://localhost:5500/` to Allowed Callback URLs and Allowed Web Origins.
2. Enable the Google and Facebook connections for that application.
3. Put your domain and Client ID in `frontend/config.js`, and set `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` (the same Client ID) in `.env`. Restart.
4. The Google and Facebook buttons in the login window now work.

## Postman
Import `postman/Smartshop.postman_collection.json`. Log in, then paste the `access_token` into the `token` variable.

## Troubleshooting
- "Cannot reach the API": the API isn't running, or the port in `frontend/config.js` doesn't match.
- "Database tables missing": run `python setup_project.py`.
- Port already in use: stop the other program, or change the port in `run_all.py` and `frontend/config.js`.

## Before production
Change `JWT_SECRET` and `DJANGO_SECRET`, set `DEBUG=False`, move to PostgreSQL, restrict CORS, and serve over HTTPS.
