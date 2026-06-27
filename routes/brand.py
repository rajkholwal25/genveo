from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import BrandProfile, Category, InfluencerProfile
from routes.auth import role_required
from utils.uploads import delete_photo, save_avatar, save_photos

brand_bp = Blueprint("brand", __name__, url_prefix="/brand")


@brand_bp.route("/dashboard")
@login_required
@role_required("brand")
def dashboard():
    categories = Category.query.order_by(Category.name).all()
    profile = BrandProfile.query.filter_by(user_id=current_user.id).first()
    return render_template(
        "brand/dashboard.html",
        categories=categories,
        profile=profile,
    )


@brand_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("brand")
def profile():
    profile = BrandProfile.query.filter_by(user_id=current_user.id).first_or_404()

    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        profile.company_name = request.form.get("company_name", profile.company_name).strip()
        category_id = request.form.get("category_id")
        if category_id:
            profile.category_id = int(category_id)
        profile.industry = request.form.get("industry", "").strip()
        profile.website = request.form.get("website", "").strip()
        profile.contact_email = request.form.get("contact_email", "").strip()
        profile.description = request.form.get("description", "").strip()
        db.session.commit()

        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            new_avatar = save_avatar(avatar_file, "brand", profile.id, profile.avatar_url)
            if new_avatar:
                profile.avatar_url = new_avatar
                db.session.commit()

        photos = request.files.getlist("photos")
        added = save_photos(photos, "brand", profile.id)
        msg = "Profile updated successfully!"
        if added:
            msg = f"Profile updated — {added} photo{'s' if added != 1 else ''} added!"
        flash(msg, "success")
        return redirect(url_for("brand.dashboard"))

    return render_template("brand/profile.html", profile=profile, categories=categories)


@brand_bp.route("/photo/<int:photo_id>/delete", methods=["POST"])
@login_required
@role_required("brand")
def delete_profile_photo(photo_id):
    profile = BrandProfile.query.filter_by(user_id=current_user.id).first_or_404()
    if delete_photo(photo_id, "brand", profile.id):
        flash("Photo removed.", "info")
    return redirect(url_for("brand.profile"))


@brand_bp.route("/category/<slug>")
@login_required
@role_required("brand")
def category_influencers(slug):
    category = Category.query.filter_by(slug=slug).first_or_404()
    influencers = (
        InfluencerProfile.query.filter_by(category_id=category.id)
        .order_by(InfluencerProfile.full_name)
        .all()
    )
    profile = BrandProfile.query.filter_by(user_id=current_user.id).first()
    return render_template(
        "brand/influencers.html",
        category=category,
        influencers=influencers,
        profile=profile,
    )
