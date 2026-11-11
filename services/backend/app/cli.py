import argparse
from app.db.session import SessionLocal
from app.modules.seed import seed
from app.core.config import get_settings
from app.db.models import Merchant, Membership, Policy
from app.modules.schemas import PolicyRules


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed", "init-store"])
    parser.add_argument("--user-id")
    parser.add_argument("--name", default="My Store")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "seed":
            print("Demo data created" if seed(db) else "Demo data already exists; unchanged")
        else:
            if not args.user_id:
                parser.error("--user-id must be an existing Supabase user UUID")
            if db.get(Merchant, "SELLER001"):
                parser.error("A store already exists; use a fresh production database")
            db.add(
                Merchant(
                    id="SELLER001",
                    name=args.name,
                    settings={"whatsapp_phone_number_id": get_settings().whatsapp_phone_number_id},
                )
            )
            db.flush()
            db.add(Membership(user_id=args.user_id, merchant_id="SELLER001", role="owner"))
            db.add(
                Policy(merchant_id="SELLER001", version=1, rules=PolicyRules().model_dump(), published=True)
            )
            db.commit()
            print("Store and owner membership created")


if __name__ == "__main__":
    main()
