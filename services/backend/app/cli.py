import argparse
import json
from sqlalchemy import text
from app.persistence.session import SessionLocal
from app.domain.seed import seed
from app.core.config import get_settings
from app.persistence.models import Merchant, Membership, Policy
from app.domain.schemas import PolicyRules


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed", "reset", "readiness", "init-store", "provision-owner"])
    parser.add_argument("--user-id")
    parser.add_argument("--name", default="My Store")
    parser.add_argument("--store")
    parser.add_argument("--confirm-store")
    args = parser.parse_args()
    s = get_settings()
    if args.command == "readiness":
        from app.integrations.whatsapp import is_configured
        state = {
            "database": False,
            "groq_configured": bool(s.groq_api_key),
            "text_model": s.groq_model,
            "vision_model": s.groq_vision_model,
            "supabase_configured": bool(s.supabase_url and s.supabase_service_role_key),
            "twilio_configured": all(
                [s.twilio_account_sid, s.twilio_auth_token, s.twilio_whatsapp_from, s.public_webhook_url]
            ),
            "ai_mode": s.ai_mode,
            "whatsapp_provider": s.whatsapp_provider,
            "whatsapp_configured": is_configured(s),
            "demo_mode": s.demo_mode,
            "live_verification": "Required: actual model response, seller session, private photo, signed incoming webhook and delivered WhatsApp follow-up.",
        }
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
                state["database"] = True
        except Exception:
            pass
        print(json.dumps(state, indent=2))
        return
    with SessionLocal() as db:
        if args.command == "seed":
            print("Demo data created" if seed(db) else "Demo data already exists; unchanged")
        elif args.command == "reset":
            from app.domain.reset import reset_demo

            reset_demo(db, args.store, args.confirm_store)
            print("Specified demo store, private evidence and workflow memory removed.")
        elif args.command == "provision-owner":
            from uuid import UUID

            if not args.user_id or not args.store:
                parser.error("--user-id and --store are required")
            UUID(args.user_id)
            if not db.get(Merchant, args.store):
                parser.error("Store does not exist")
            membership = db.get(Membership, args.user_id)
            if membership and membership.merchant_id != args.store:
                parser.error("This user already belongs to another store")
            if not membership:
                db.add(Membership(user_id=args.user_id, merchant_id=args.store, role="owner"))
            from app.domain.common import audit

            audit(db, args.store, "local-operator", "membership.provisioned", args.user_id)
            db.commit()
            print("Owner membership provisioned")
        else:
            if not args.user_id:
                parser.error("--user-id must be an existing Supabase user UUID")
            if db.get(Merchant, "SELLER001"):
                parser.error("A store already exists; use a fresh database")
            db.add(Merchant(id="SELLER001", name=args.name, settings={}))
            db.flush()
            db.add(Membership(user_id=args.user_id, merchant_id="SELLER001", role="owner"))
            db.add(
                Policy(merchant_id="SELLER001", version=1, rules=PolicyRules().model_dump(), published=True)
            )
            db.commit()
            print("Store and owner membership created")


if __name__ == "__main__":
    main()
