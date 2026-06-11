from app.core.config import get_settings
from app.db import SessionLocal
from app.seed import seed_demo_data


def main() -> None:
    if not get_settings().demo_seed_enabled:
        print("Demo seeding disabled. Set DEMO_SEED_ENABLED=true to seed demo data.")
        return
    db = SessionLocal()
    try:
        seed_demo_data(db)
        print("Demo data seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
