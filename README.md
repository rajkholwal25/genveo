# Influence Connect

A Flask web app connecting **Brands** with **Influencers** — browse by category, view stats, pricing, and contact details.

## Quick Start (Local)

```bash
cd influence-connect
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:5000**

---

## Connect Supabase Database

This app uses **Supabase PostgreSQL** via a connection string (same as any Postgres database).

### Step 1 — Get your Supabase connection string

1. Open [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Go to **Project Settings** → **Database**
4. Under **Connection string**, choose **URI**
5. Copy the string and replace `[YOUR-PASSWORD]` with your database password

**Use Session pooler (port 5432)** — best for Flask:

```
postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
```

### Step 2 — Create `.env` file

```bash
copy .env.example .env    # Windows
# cp .env.example .env    # Mac/Linux
```

Edit `.env`:

```env
DATABASE_URL=postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
SECRET_KEY=your-long-random-secret-key
```

### Step 3 — Install dependencies & run

```bash
pip install -r requirements.txt
python run.py
```

On first run, Flask will **auto-create all tables** in Supabase and seed demo data.

You can verify in Supabase → **Table Editor** — you should see `users`, `categories`, `brand_profiles`, `influencer_profiles`.

### Optional — Run SQL manually in Supabase

If you prefer to create tables yourself, run `supabase/schema.sql` in **Supabase → SQL Editor**.

---

## Supabase + GitHub Integration

If you linked GitHub to Supabase:

- Supabase stores your **database** in the cloud
- Your **Flask app** (on your PC or a host like Render/Railway) connects using `DATABASE_URL` in `.env`
- The GitHub link does **not** auto-connect Flask — you still set `DATABASE_URL` wherever the app runs

### Deploying with Supabase (e.g. Render / Railway)

Add these **environment variables** on your hosting platform:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Your Supabase Session pooler URI |
| `SECRET_KEY` | A long random secret string |

---

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@influence.com | admin123 |
| Brand | brand@demo.com | demo123 |
| Influencer | kavya_glam@demo.com | demo123 |

## Features

- **3 login types:** Admin, Brand, Influencer
- **Brand dashboard:** Category icons → influencer cards
- **Influencer cards:** Instagram, followers, monthly reach, email, monthly pricing
- **Influencer signup:** Set category, stats, and monthly rate
- **Influencer dashboard:** Browse all registered brands
- **Admin panel:** Manage users & add categories

## Tech Stack

- Python Flask
- Flask-Login (auth)
- Flask-SQLAlchemy + **Supabase PostgreSQL**
- HTML/CSS/JS (custom animated UI)
