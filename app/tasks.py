import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Contact, Invoice
from app.odoo_client import OdooClient


@celery_app.task(name="app.tasks.sync_contacts")
def sync_contacts():
    """
    Task to sync contacts from Odoo to local database.
    Inserts new contacts, updates existing ones, and deletes removed contacts.
    """
    print("Starting contact sync from Odoo...")

    try:
        # Run async code in sync context
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_sync_contacts_async())
        print(f"Contact sync completed: {result}")
        return result

    except Exception as e:
        error_msg = f"Error syncing contacts: {str(e)}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


async def _sync_contacts_async():
    """Async implementation of contact sync"""
    db: Session = SessionLocal()

    try:
        # Initialize Odoo client and fetch contacts
        odoo_client = OdooClient()
        #TODO Optimization: Better not to keep all contacts in memory in the same time.
        odoo_contacts = await odoo_client.get_all_contacts()

        if not odoo_contacts:
            return {"status": "success", "message": "No contacts found in Odoo"}

        # Get all existing contacts from database
        existing_contacts = db.query(Contact).all()
        existing_odoo_ids = {contact.odoo_id for contact in existing_contacts}
        fetched_odoo_ids = {contact["id"] for contact in odoo_contacts}

        inserted = 0
        updated = 0
        deleted = 0

        # Insert or update contacts
        for odoo_contact in odoo_contacts:
            odoo_id = odoo_contact["id"]

            # Parse write_date
            write_date = None
            if odoo_contact.get("write_date"):
                try:
                    write_date = datetime.fromisoformat(odoo_contact["write_date"].replace("Z", "+00:00"))
                except Exception:
                    pass

            # Helper function to convert Odoo False to None
            def odoo_value(value):
                """Convert Odoo's False to None for optional string fields"""
                return None if value is False else value

            # Check if contact exists
            existing_contact = db.query(Contact).filter(Contact.odoo_id == odoo_id).first()

            if existing_contact:
                # Update existing contact
                existing_contact.name = odoo_contact.get("name") or ""
                existing_contact.email = odoo_value(odoo_contact.get("email"))
                existing_contact.phone = odoo_value(odoo_contact.get("phone"))
                existing_contact.write_date = write_date
                existing_contact.updated_at = datetime.utcnow()
                updated += 1
            else:
                # Insert new contact
                new_contact = Contact(
                    odoo_id=odoo_id,
                    name=odoo_contact.get("name") or "",
                    email=odoo_value(odoo_contact.get("email")),
                    phone=odoo_value(odoo_contact.get("phone")),
                    write_date=write_date
                )
                db.add(new_contact)
                inserted += 1

        # Delete contacts that no longer exist in Odoo
        contacts_to_delete = existing_odoo_ids - fetched_odoo_ids
        if contacts_to_delete:
            db.query(Contact).filter(Contact.odoo_id.in_(contacts_to_delete)).delete(synchronize_session=False)
            deleted = len(contacts_to_delete)

        db.commit()

        return {
            "status": "success",
            "message": f"Synced {len(odoo_contacts)} contacts from Odoo",
            "inserted": inserted,
            "updated": updated,
            "deleted": deleted,
            "total": len(odoo_contacts)
        }

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


@celery_app.task(name="app.tasks.sync_invoices")
def sync_invoices():
    """
    Task to sync invoices from Odoo to local database.
    Inserts new invoices, updates existing ones, and deletes removed invoices.
    """
    print("Starting invoice sync from Odoo...")

    try:
        # Run async code in sync context
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_sync_invoices_async())
        print(f"Invoice sync completed: {result}")
        return result

    except Exception as e:
        error_msg = f"Error syncing invoices: {str(e)}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


async def _sync_invoices_async():
    """Async implementation of invoice sync"""
    db: Session = SessionLocal()

    try:
        # Initialize Odoo client and fetch invoices
        odoo_client = OdooClient()
        odoo_invoices = await odoo_client.get_all_invoices()

        if not odoo_invoices:
            return {"status": "success", "message": "No invoices found in Odoo"}

        # Get all existing invoices from database
        existing_invoices = db.query(Invoice).all()
        existing_odoo_ids = {invoice.odoo_id for invoice in existing_invoices}
        fetched_odoo_ids = {invoice["id"] for invoice in odoo_invoices}

        inserted = 0
        updated = 0
        deleted = 0

        # Helper function to convert Odoo False to None
        def odoo_value(value):
            """Convert Odoo's False to None for optional fields"""
            return None if value is False else value

        # Helper to parse datetime
        def parse_datetime(date_str):
            """Parse datetime string from Odoo"""
            if not date_str or date_str is False:
                return None
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                return None

        # Helper to extract value from tuple (partner_id and currency_id are tuples)
        def extract_tuple_values(value):
            """Extract ID and name from Odoo tuple [id, name]"""
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                return value[0], value[1]
            elif isinstance(value, (list, tuple)) and len(value) == 1:
                return value[0], None
            return None, None

        # Insert or update invoices
        for odoo_invoice in odoo_invoices:
            odoo_id = odoo_invoice["id"]

            # Parse dates
            invoice_date = parse_datetime(odoo_invoice.get("invoice_date"))
            write_date = parse_datetime(odoo_invoice.get("write_date"))
            create_date = parse_datetime(odoo_invoice.get("create_date"))

            # Extract partner info
            partner_id, partner_name = extract_tuple_values(odoo_invoice.get("partner_id"))

            # Extract currency info
            currency_id, currency_name = extract_tuple_values(odoo_invoice.get("currency_id"))

            # Check if invoice exists
            existing_invoice = db.query(Invoice).filter(Invoice.odoo_id == odoo_id).first()

            if existing_invoice:
                # Update existing invoice
                existing_invoice.name = odoo_invoice.get("name") or ""
                existing_invoice.move_type = odoo_invoice.get("move_type") or "out_invoice"
                existing_invoice.invoice_date = invoice_date
                existing_invoice.partner_id = partner_id
                existing_invoice.partner_name = partner_name
                existing_invoice.amount_total = odoo_invoice.get("amount_total")
                existing_invoice.amount_residual = odoo_invoice.get("amount_residual")
                existing_invoice.state = odoo_invoice.get("state")
                existing_invoice.currency_id = currency_id
                existing_invoice.currency_name = currency_name
                existing_invoice.write_date = write_date
                existing_invoice.create_date = create_date
                existing_invoice.updated_at = datetime.utcnow()
                updated += 1
            else:
                # Insert new invoice
                new_invoice = Invoice(
                    odoo_id=odoo_id,
                    name=odoo_invoice.get("name") or "",
                    move_type=odoo_invoice.get("move_type") or "out_invoice",
                    invoice_date=invoice_date,
                    partner_id=partner_id,
                    partner_name=partner_name,
                    amount_total=odoo_invoice.get("amount_total"),
                    amount_residual=odoo_invoice.get("amount_residual"),
                    state=odoo_invoice.get("state"),
                    currency_id=currency_id,
                    currency_name=currency_name,
                    write_date=write_date,
                    create_date=create_date
                )
                db.add(new_invoice)
                inserted += 1

        # Delete invoices that no longer exist in Odoo
        invoices_to_delete = existing_odoo_ids - fetched_odoo_ids
        if invoices_to_delete:
            db.query(Invoice).filter(Invoice.odoo_id.in_(invoices_to_delete)).delete(synchronize_session=False)
            deleted = len(invoices_to_delete)

        db.commit()

        return {
            "status": "success",
            "message": f"Synced {len(odoo_invoices)} invoices from Odoo",
            "inserted": inserted,
            "updated": updated,
            "deleted": deleted,
            "total": len(odoo_invoices)
        }

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


@celery_app.task(name="app.tasks.test_task")
def test_task():
    """
    Test task to verify Celery workers and Redis are working.
    """
    print("test task was executed")
    return {"status": "success", "message": "test task was executed"}
