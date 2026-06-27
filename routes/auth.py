from functools import wraps

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models import BrandProfile, Category, InfluencerProfile, User
from utils.auth import (
    find_user_by_login,
    is_valid_mobile,
    is_valid_username,
    normalize_mobile,
    normalize_username,
)
from utils.instagram import normalize_stat, parse_instagram_handle, instagram_profile_url

auth_bp = __import__("flask").Blueprint("auth", __name__)


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in to continue.", "info")
                return redirect(url_for("auth.login", next=request.path))
            if current_user.role not in roles:
                area = roles[0].capitalize()
                flash(f"The {area} area isn't available for your account. Here's your dashboard.", "info")
                return redirect(_dashboard_for_role(current_user.role))
            return f(*args, **kwargs)

        return wrapped

    return decorator


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_dashboard_for_role(current_user.role))

    role = request.args.get("role", "brand")
    if role not in ("admin", "brand", "influencer"):
        role = "brand"

    if request.method == "POST":
        login_id = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", role)

        user = find_user_by_login(login_id, role)
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or _dashboard_for_role(user.role))

        flash("Invalid login details or password for this role.", "error")

    return render_template("auth/login.html", role=role)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(_dashboard_for_role(current_user.role))

    role = request.args.get("role", "brand")
    if role not in ("brand", "influencer"):
        role = "brand"

    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = normalize_username(request.form.get("username", ""))
        mobile = normalize_mobile(request.form.get("mobile", ""))
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", role)

        if not email or not password or not username or not mobile:
            flash("Email, username, mobile, and password are required.", "error")
        elif not is_valid_username(username):
            flash("Username must be 3–30 characters (letters, numbers, underscore only).", "error")
        elif not is_valid_mobile(mobile):
            flash("Enter a valid 10-digit Indian mobile number.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "error")
        elif User.query.filter_by(username=username).first():
            flash("This username is already taken.", "error")
        elif User.query.filter_by(mobile=mobile).first():
            flash("This mobile number is already registered.", "error")
        elif role == "brand":
            company_name = request.form.get("company_name", "").strip()
            category_id = request.form.get("category_id")
            if not company_name:
                flash("Company name is required.", "error")
            elif not category_id:
                flash("Please choose the category your brand wants creators in.", "error")
            else:
                user = User(email=email, username=username, mobile=mobile, role="brand")
                user.set_password(password)
                db.session.add(user)
                db.session.flush()
                profile = BrandProfile(
                    user_id=user.id,
                    company_name=company_name,
                    category_id=int(category_id),
                    industry=request.form.get("industry", "").strip(),
                    website=request.form.get("website", "").strip(),
                    description=request.form.get("description", "").strip(),
                    contact_email=email,
                )
                db.session.add(profile)
                db.session.commit()
                login_user(user)
                flash("Welcome! Your brand account is ready.", "success")
                return redirect(url_for("brand.dashboard"))
        elif role == "influencer":
            full_name = request.form.get("full_name", "").strip()
            category_id = request.form.get("category_id")
            insta_input = request.form.get("instagram_handle", "").strip()
            instagram = parse_instagram_handle(insta_input)
            reel = request.form.get("reel_pricing", "0")
            story = request.form.get("story_pricing", "0")
            post = request.form.get("post_pricing", "0")
            followers = normalize_stat(request.form.get("followers", ""))
            monthly_reach = normalize_stat(request.form.get("monthly_reach", ""))

            if not full_name or not category_id or not instagram:
                flash("Name, category, and Instagram URL or handle are required.", "error")
            else:
                try:
                    reel_val = float(reel)
                    story_val = float(story)
                    post_val = float(post)
                    if reel_val <= 0 and story_val <= 0 and post_val <= 0:
                        flash("Enter at least one pricing amount.", "error")
                    else:
                        user = User(
                            email=email,
                            username=username,
                            mobile=mobile,
                            role="influencer",
                        )
                        user.set_password(password)
                        db.session.add(user)
                        db.session.flush()
                        profile = InfluencerProfile(
                            user_id=user.id,
                            full_name=full_name,
                            category_id=int(category_id),
                            instagram_handle=instagram,
                            instagram_url=instagram_profile_url(insta_input),
                            followers=followers,
                            monthly_reach=monthly_reach,
                            reel_pricing=reel_val,
                            story_pricing=story_val,
                            post_pricing=post_val,
                            bio=request.form.get("bio", "").strip(),
                        )
                        db.session.add(profile)
                        db.session.commit()
                        login_user(user)
                        flash("Welcome! Your influencer profile is live.", "success")
                        return redirect(url_for("influencer.dashboard"))
                except ValueError:
                    flash("Please enter valid pricing for reel, story, and post.", "error")

    return render_template("auth/signup.html", role=role, categories=categories)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(_dashboard_for_role(current_user.role))

    if request.method == "POST":
        from utils.email import make_reset_token, password_reset_html, send_email

        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = make_reset_token(user.email)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            name = user.username or user.email.split("@")[0]
            send_email(user.email, "Reset your Genveo password", password_reset_html(name, reset_url))

        # Same response whether or not the email exists (avoid account enumeration)
        flash("If an account exists for that email, a reset link is on its way.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    from utils.email import verify_reset_token

    email = verify_reset_token(token)
    if not email:
        flash("This reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("We couldn't find that account.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            user.set_password(password)
            db.session.commit()
            flash("Your password has been updated. Please sign in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token, email=email)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


def _dashboard_for_role(role: str) -> str:
    routes = {
        "admin": "admin.dashboard",
        "brand": "brand.dashboard",
        "influencer": "influencer.dashboard",
    }
    return url_for(routes.get(role, "main.index"))
