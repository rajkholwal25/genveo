from flask import Flask, render_template
from flask_login import current_user

from config import Config
from extensions import db, login_manager
from models import User


def _register_error_handlers(app):
    def _home():
        if current_user.is_authenticated:
            routes = {
                "admin": "admin.dashboard",
                "brand": "brand.dashboard",
                "influencer": "influencer.dashboard",
            }
            return routes.get(current_user.role, "main.index"), "Go to dashboard"
        return "main.index", "Back to home"

    from flask import url_for

    def _render(code, title, message):
        endpoint, label = _home()
        return (
            render_template(
                "error.html",
                code=code,
                title=title,
                message=message,
                home_url=url_for(endpoint),
                home_label=label,
            ),
            code,
        )

    @app.errorhandler(403)
    def forbidden(_e):
        return _render(403, "Access denied", "You don't have permission to view this page.")

    @app.errorhandler(404)
    def not_found(_e):
        return _render(404, "Page not found", "The page you're looking for doesn't exist or has moved.")

    @app.errorhandler(500)
    def server_error(_e):
        return _render(500, "Something went wrong", "An unexpected error occurred. Please try again.")


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.brand import brand_bp
    from routes.influencer import influencer_bp
    from routes.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(brand_bp)
    app.register_blueprint(influencer_bp)
    app.register_blueprint(admin_bp)

    _register_error_handlers(app)

    with app.app_context():
        db.create_all()
        _migrate_pricing_columns()
        _migrate_profile_stats()
        _migrate_user_auth_columns()
        _migrate_category_icon_url()
        _migrate_avatar_columns()
        _migrate_brand_category()
        _seed_data()

    return app


def _migrate_category_icon_url():
    """Add categories.icon_url column for uploaded category icons."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "categories" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("categories")}
    if "icon_url" not in cols:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE categories ADD COLUMN icon_url VARCHAR(255)"))


def _migrate_avatar_columns():
    """Add avatar_url to brand_profiles and influencer_profiles."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    for table in ("brand_profiles", "influencer_profiles"):
        if table not in insp.get_table_names():
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "avatar_url" not in cols:
            with db.engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN avatar_url VARCHAR(255)"))


def _migrate_brand_category():
    """Add brand_profiles.category_id and give the demo brand a category."""
    from sqlalchemy import inspect, text

    from models import BrandProfile, Category

    insp = inspect(db.engine)
    if "brand_profiles" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("brand_profiles")}
    if "category_id" not in cols:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE brand_profiles ADD COLUMN category_id INTEGER"))

    # Backfill the demo brand so the matching demo works out of the box.
    demo = BrandProfile.query.filter_by(company_name="Glow Cosmetics").first()
    if demo and not demo.category_id:
        makeup = Category.query.filter_by(slug="makeup").first()
        if makeup:
            demo.category_id = makeup.id
            db.session.commit()


def _migrate_pricing_columns():
    """Add reel/story/post pricing columns; migrate from old monthly_pricing if present."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "influencer_profiles" not in insp.get_table_names():
        return

    cols = {c["name"] for c in insp.get_columns("influencer_profiles")}

    if "reel_pricing" not in cols:
        stmts = [
            "ALTER TABLE influencer_profiles ADD COLUMN reel_pricing DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE influencer_profiles ADD COLUMN story_pricing DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE influencer_profiles ADD COLUMN post_pricing DOUBLE PRECISION DEFAULT 0",
        ]
        if "monthly_pricing" in cols:
            stmts.append(
                "UPDATE influencer_profiles SET reel_pricing = monthly_pricing, "
                "story_pricing = ROUND(monthly_pricing * 0.35), "
                "post_pricing = ROUND(monthly_pricing * 0.5)"
            )
        with db.engine.begin() as conn:
            for sql in stmts:
                conn.execute(text(sql))
        cols = {c["name"] for c in insp.get_columns("influencer_profiles")}

    if "monthly_pricing" in cols:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE influencer_profiles DROP COLUMN monthly_pricing"))


def _format_int_stat(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value) if value else "—"
    if n <= 0:
        return "—"
    if n >= 1_000_000_000:
        s = f"{n / 1_000_000_000:.1f}B"
    elif n >= 1_000_000:
        s = f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        s = f"{n / 1_000:.1f}K"
    else:
        return str(n)
    return s.replace(".0K", "K").replace(".0M", "M").replace(".0B", "B")


def _migrate_profile_stats():
    """Convert followers/reach to text (1.1M, 125K); add instagram_url column."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "influencer_profiles" not in insp.get_table_names():
        return

    cols = {c["name"] for c in insp.get_columns("influencer_profiles")}

    if "instagram_url" not in cols:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE influencer_profiles ADD COLUMN instagram_url VARCHAR(200)"))

    if "postgresql" not in str(db.engine.url):
        return

    with db.engine.connect() as conn:
        types = {
            row[0]: row[1]
            for row in conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'influencer_profiles' "
                "AND column_name IN ('followers', 'monthly_reach')"
            ))
        }

    if types.get("followers") != "integer":
        return

    stat_case = """
        CASE
            WHEN {col} >= 1000000000 THEN TRIM(TRAILING '.0' FROM ROUND({col}::numeric / 1000000000, 1)::text) || 'B'
            WHEN {col} >= 1000000 THEN TRIM(TRAILING '.0' FROM ROUND({col}::numeric / 1000000, 1)::text) || 'M'
            WHEN {col} >= 1000 THEN TRIM(TRAILING '.0' FROM ROUND({col}::numeric / 1000, 1)::text) || 'K'
            ELSE {col}::text
        END
    """

    with db.engine.begin() as conn:
        conn.execute(text(
            f"ALTER TABLE influencer_profiles ALTER COLUMN followers TYPE VARCHAR(30) "
            f"USING ({stat_case.format(col='followers')})"
        ))
        conn.execute(text(
            f"ALTER TABLE influencer_profiles ALTER COLUMN monthly_reach TYPE VARCHAR(30) "
            f"USING ({stat_case.format(col='monthly_reach')})"
        ))
        conn.execute(text(
            "UPDATE influencer_profiles SET instagram_url = 'https://instagram.com/' || instagram_handle "
            "WHERE instagram_url IS NULL OR instagram_url = ''"
        ))


def _migrate_user_auth_columns():
    """Add username/mobile columns and backfill usernames for existing users."""
    import re

    from sqlalchemy import inspect, text

    from models import User

    insp = inspect(db.engine)
    if "users" not in insp.get_table_names():
        return

    cols = {c["name"] for c in insp.get_columns("users")}
    if "username" not in cols:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(80)"))
            conn.execute(text("ALTER TABLE users ADD COLUMN mobile VARCHAR(20)"))

    users = User.query.filter(
        (User.username.is_(None)) | (User.username == "")
    ).all()
    for user in users:
        base = re.sub(r"[^a-z0-9_]", "", user.email.split("@")[0].lower()) or "user"
        candidate = base[:30]
        n = 1
        while User.query.filter_by(username=candidate).filter(User.id != user.id).first():
            suffix = str(n)
            candidate = f"{base[: 30 - len(suffix)]}{suffix}"
            n += 1
        user.username = candidate

    changed = bool(users)
    for user in User.query.filter(User.mobile.is_(None)).all():
        candidate = f"9876{user.id:06d}"
        if not User.query.filter_by(mobile=candidate).filter(User.id != user.id).first():
            user.mobile = candidate
            changed = True

    if changed:
        db.session.commit()

    demo_accounts = {
        "admin@influence.com": {"username": "admin", "mobile": "9000000001"},
        "brand@demo.com": {"username": "glowbrand", "mobile": "9000000002"},
    }
    demo_changed = False
    for email, fields in demo_accounts.items():
        user = User.query.filter_by(email=email).first()
        if not user:
            continue
        for key, value in fields.items():
            if getattr(user, key) != value:
                setattr(user, key, value)
                demo_changed = True
    if demo_changed:
        db.session.commit()


def _seed_data():
    from models import BrandProfile, Category, InfluencerProfile

    if Category.query.first():
        return

    categories = [
        Category(name="Sports", slug="sports", icon="⚽", color="#ef4444"),
        Category(name="Study", slug="study", icon="📚", color="#3b82f6"),
        Category(name="Makeup", slug="makeup", icon="💄", color="#ec4899"),
        Category(name="Fashion", slug="fashion", icon="👗", color="#a855f7"),
        Category(name="Tech", slug="tech", icon="💻", color="#06b6d4"),
        Category(name="Food", slug="food", icon="🍔", color="#f59e0b"),
        Category(name="Travel", slug="travel", icon="✈️", color="#10b981"),
        Category(name="Fitness", slug="fitness", icon="💪", color="#f97316"),
    ]
    db.session.add_all(categories)
    db.session.flush()

    admin = User(email="admin@influence.com", role="admin", username="admin", mobile="9000000001")
    admin.set_password("admin123")
    db.session.add(admin)

    # Demo brand
    brand_user = User(email="brand@demo.com", role="brand", username="glowbrand", mobile="9000000002")
    brand_user.set_password("demo123")
    db.session.add(brand_user)
    db.session.flush()
    db.session.add(
        BrandProfile(
            user_id=brand_user.id,
            company_name="Glow Cosmetics",
            industry="Beauty",
            website="https://glowcosmetics.com",
            description="Premium beauty brand looking for authentic creators.",
            contact_email="brand@demo.com",
        )
    )

    # Demo: slug, name, insta, followers, reach, reel, story, post (stats as strings)
    demo_influencers = [
        ("sports", "Rahul Sharma", "rahul_fitness", "125K", "450K", 15000, 5000, 8000),
        ("sports", "Priya Athlete", "priya_runs", "89K", "320K", 12000, 4000, 6000),
        ("study", "Study With Arjun", "arjun_studies", "210K", "780K", 25000, 8000, 12000),
        ("study", "Neha Educates", "neha_edu", "156K", "520K", 18000, 6000, 10000),
        ("makeup", "Glam by Kavya", "kavya_glam", "340K", "1.2M", 45000, 15000, 25000),
        ("makeup", "Beauty Rituals", "beauty_rituals", "275K", "950K", 35000, 12000, 20000),
        ("fashion", "Style Diaries", "style_diaries", "198K", "680K", 22000, 7000, 11000),
        ("tech", "Tech Talk India", "techtalk_in", "420K", "1.5M", 55000, 18000, 30000),
    ]

    cat_map = {c.slug: c.id for c in categories}
    for idx, (slug, name, insta, followers, reach, reel, story, post) in enumerate(
        demo_influencers, start=1
    ):
        user = User(
            email=f"{insta}@demo.com",
            role="influencer",
            username=insta,
            mobile=f"9876{idx:06d}",
        )
        user.set_password("demo123")
        db.session.add(user)
        db.session.flush()
        db.session.add(
            InfluencerProfile(
                user_id=user.id,
                full_name=name,
                category_id=cat_map[slug],
                instagram_handle=insta,
                instagram_url=f"https://instagram.com/{insta}",
                followers=followers,
                monthly_reach=reach,
                reel_pricing=reel,
                story_pricing=story,
                post_pricing=post,
                bio=f"Content creator specializing in {slug}. Available for brand collaborations.",
            )
        )

    db.session.commit()
