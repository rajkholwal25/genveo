import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from models import BrandProfile, Category, InfluencerProfile, ProfilePhoto, User
from routes.auth import role_required
from utils.instagram import instagram_profile_url, normalize_stat, parse_instagram_handle
from utils.uploads import delete_icon, upload_icon

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    brands = BrandProfile.query.order_by(BrandProfile.company_name).all()
    influencers = InfluencerProfile.query.order_by(InfluencerProfile.full_name).all()
    return render_template(
        "admin/dashboard.html",
        users=users,
        categories=categories,
        brands=brands,
        influencers=influencers,
        stats={
            "users": len(users),
            "brands": len(brands),
            "influencers": len(influencers),
            "categories": len(categories),
        },
    )


# ----------------------------- helpers --------------------------------------

def _unique_username(email: str) -> str:
    base = re.sub(r"[^a-z0-9_]", "", email.split("@")[0].lower()) or "user"
    candidate = base[:30]
    n = 1
    while User.query.filter_by(username=candidate).first():
        suffix = str(n)
        candidate = f"{base[: 30 - len(suffix)]}{suffix}"
        n += 1
    return candidate


def _unique_mobile() -> str:
    n = User.query.count() + 1
    while True:
        candidate = f"9700{n:06d}"
        if not User.query.filter_by(mobile=candidate).first():
            return candidate
        n += 1


def _purge_photos(owner_type: str, owner_id: int) -> None:
    """Remove a profile's gallery photos from storage and DB before deletion."""
    from utils.uploads import delete_photo

    photos = ProfilePhoto.query.filter_by(owner_type=owner_type, owner_id=owner_id).all()
    for photo in photos:
        delete_photo(photo.id, owner_type, owner_id)


# ----------------------------- categories -----------------------------------

@admin_bp.route("/category/add", methods=["POST"])
@login_required
@role_required("admin")
def add_category():
    name = request.form.get("name", "").strip()
    icon = request.form.get("icon", "✨").strip() or "✨"
    color = request.form.get("color", "#10b981").strip()
    icon_file = request.files.get("icon_file")

    if not name:
        flash("Category name is required.", "error")
    elif Category.query.filter_by(name=name).first():
        flash("Category already exists.", "error")
    else:
        icon_url = upload_icon(icon_file) if icon_file else None
        slug = name.lower().replace(" ", "-").replace("/", "-")
        db.session.add(Category(name=name, slug=slug, icon=icon, icon_url=icon_url, color=color))
        db.session.commit()
        flash(f'Category "{name}" added!', "success")

    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/category/<int:category_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.influencers:
        flash(
            f'Cannot delete "{category.name}" — {len(category.influencers)} influencer(s) use it.',
            "error",
        )
        return redirect(url_for("admin.dashboard"))
    delete_icon(category.icon_url)
    db.session.delete(category)
    db.session.commit()
    flash(f'Category "{category.name}" deleted.', "info")
    return redirect(url_for("admin.dashboard"))


# ------------------------------- brands -------------------------------------

@admin_bp.route("/brand/add", methods=["POST"])
@login_required
@role_required("admin")
def add_brand():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    company_name = request.form.get("company_name", "").strip()

    if not email or not password or not company_name:
        flash("Email, password, and company name are required.", "error")
    elif User.query.filter_by(email=email).first():
        flash("An account with this email already exists.", "error")
    else:
        user = User(
            email=email,
            username=_unique_username(email),
            mobile=_unique_mobile(),
            role="brand",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        category_id = request.form.get("category_id")
        db.session.add(
            BrandProfile(
                user_id=user.id,
                company_name=company_name,
                category_id=int(category_id) if category_id else None,
                industry=request.form.get("industry", "").strip(),
                website=request.form.get("website", "").strip(),
                description=request.form.get("description", "").strip(),
                contact_email=email,
            )
        )
        db.session.commit()
        flash(f'Brand "{company_name}" created.', "success")

    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/brand/<int:brand_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_brand(brand_id):
    brand = BrandProfile.query.get_or_404(brand_id)
    name = brand.company_name
    _purge_photos("brand", brand.id)
    db.session.delete(brand.user)  # cascade removes the brand profile
    db.session.commit()
    flash(f'Brand "{name}" deleted.', "info")
    return redirect(url_for("admin.dashboard"))


# ---------------------------- influencers -----------------------------------

@admin_bp.route("/influencer/add", methods=["POST"])
@login_required
@role_required("admin")
def add_influencer():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    full_name = request.form.get("full_name", "").strip()
    category_id = request.form.get("category_id")
    insta_input = request.form.get("instagram_handle", "").strip()

    if not email or not password or not full_name or not category_id or not insta_input:
        flash("Email, password, name, category, and Instagram are required.", "error")
        return redirect(url_for("admin.dashboard"))
    if User.query.filter_by(email=email).first():
        flash("An account with this email already exists.", "error")
        return redirect(url_for("admin.dashboard"))

    try:
        reel = float(request.form.get("reel_pricing", "0") or 0)
        story = float(request.form.get("story_pricing", "0") or 0)
        post = float(request.form.get("post_pricing", "0") or 0)
    except ValueError:
        flash("Enter valid pricing amounts.", "error")
        return redirect(url_for("admin.dashboard"))

    user = User(
        email=email,
        username=_unique_username(email),
        mobile=_unique_mobile(),
        role="influencer",
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(
        InfluencerProfile(
            user_id=user.id,
            full_name=full_name,
            category_id=int(category_id),
            instagram_handle=parse_instagram_handle(insta_input),
            instagram_url=instagram_profile_url(insta_input),
            followers=normalize_stat(request.form.get("followers", "")),
            monthly_reach=normalize_stat(request.form.get("monthly_reach", "")),
            reel_pricing=reel,
            story_pricing=story,
            post_pricing=post,
            bio=request.form.get("bio", "").strip(),
        )
    )
    db.session.commit()
    flash(f'Influencer "{full_name}" created.', "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/influencer/<int:influencer_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_influencer(influencer_id):
    influencer = InfluencerProfile.query.get_or_404(influencer_id)
    name = influencer.full_name
    _purge_photos("influencer", influencer.id)
    db.session.delete(influencer.user)
    db.session.commit()
    flash(f'Influencer "{name}" deleted.', "info")
    return redirect(url_for("admin.dashboard"))
