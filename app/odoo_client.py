import httpx
from typing import Optional, List, Dict, Any
from app.config import get_settings

settings = get_settings()


class OdooClient:
    """Client for interacting with Odoo API"""

    def __init__(self):
        self.base_url = settings.ODOO_URL
        self.db = settings.ODOO_DB
        self.username = settings.ODOO_USERNAME
        self.password = settings.ODOO_PASSWORD
        self.session_id: Optional[str] = None
        self.user_id: Optional[int] = None

    async def authenticate(self) -> bool:
        """Authenticate with Odoo and get session ID"""
        url = f"{self.base_url}/web/session/authenticate"

        payload = {
            "jsonrpc": "2.0",
            "params": {
                "db": self.db,
                "login": self.username,
                "password": self.password
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()

            if "result" in result and result["result"].get("uid"):
                self.user_id = result["result"]["uid"]
                # Extract session_id from cookies
                cookies = response.cookies
                if "session_id" in cookies:
                    self.session_id = cookies["session_id"]
                    return True

        return False

    async def get_contacts(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Fetch contacts from Odoo"""
        if not self.session_id or not self.user_id:
            await self.authenticate()

        url = f"{self.base_url}/jsonrpc"

        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    self.db,
                    self.user_id,
                    self.password,
                    "res.partner",
                    "search_read",
                    [[]],
                    {
                        "fields": ["id", "name", "email", "phone", "write_date"],
                        "limit": limit,
                        "offset": offset
                    }
                ]
            }
        }

        cookies = {"session_id": self.session_id}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, cookies=cookies)
            response.raise_for_status()

            result = response.json()

            if "result" in result:
                return result["result"]

        return []

    async def get_all_contacts(self) -> List[Dict[str, Any]]:
        """Fetch all contacts from Odoo with pagination"""
        all_contacts = []
        offset = 0
        limit = 100

        while True:
            contacts = await self.get_contacts(limit=limit, offset=offset)

            if not contacts:
                break

            all_contacts.extend(contacts)
            offset += limit

            # If we got less than limit, we've reached the end
            if len(contacts) < limit:
                break

        return all_contacts

    async def get_invoices(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Fetch invoices from Odoo"""
        if not self.session_id or not self.user_id:
            await self.authenticate()

        url = f"{self.base_url}/jsonrpc"

        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [
                    self.db,
                    self.user_id,
                    self.password,
                    "account.move",
                    "search_read",
                    [[["move_type", "=", "out_invoice"]]],
                    {
                        "fields": [
                            "id",
                            "name",
                            "move_type",
                            "invoice_date",
                            "partner_id",
                            "amount_total",
                            "amount_residual",
                            "state",
                            "currency_id",
                            "write_date",
                            "create_date"
                        ],
                        "limit": limit,
                        "offset": offset,
                        "order": "write_date desc"
                    }
                ]
            }
        }

        cookies = {"session_id": self.session_id}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, cookies=cookies)
            response.raise_for_status()

            result = response.json()

            if "result" in result:
                return result["result"]

        return []

    async def get_all_invoices(self) -> List[Dict[str, Any]]:
        """Fetch all invoices from Odoo with pagination"""
        all_invoices = []
        offset = 0
        limit = 100

        while True:
            invoices = await self.get_invoices(limit=limit, offset=offset)

            if not invoices:
                break

            all_invoices.extend(invoices)
            offset += limit

            # If we got less than limit, we've reached the end
            if len(invoices) < limit:
                break

        return all_invoices
