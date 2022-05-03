
import datetime
import logging
import uuid
import time

import firebase_admin
import firebase_admin.auth

from .. state import State

from . referral import Referrals

logger = logging.getLogger("admin.user")
logger.setLevel(logging.INFO)

def check_domain(email, domains):
    try:
        user_domain = email.split("@", 1)[1]
    except:
        logger.info("Badly formed email address")
        raise RuntimeError("Badly formed email address")
    if not user_domain in domains:
        logger.info("User registered email with wrong domain")
        raise RuntimeError("Bad domain")

class AuthHeaderFailure(Exception):
    pass

class EmailNotVerified(Exception):
    pass

class BadDomain(Exception):
    pass

class RequestAuth:
    def __init__(self, user, scope, auth):
        self.auth = auth
        self.user = user
        self.scope = scope
    def verify_scope(self, scope):
        if scope not in self.scope:
            logger.info("Scope forbidden: %s", scope)
            raise this.scope_invalid()
    def scope_invalid(self):
        return web.HTTPForbidden(
            text=json.dumps({
                "message": "You do not have permission",
                "code": "no-permission"
            }),
            content_type="application/json"
        )
    
class UserAdmin:
    def __init__(self, config, store):

        try:
            self.domains = set(config["restrict-user-domains"])
            logger.info("Restricted user domains: %s", str(self.domains))
        except:
            self.domains = None
            logger.info("No user domain restriction")

        self.store = store

        self.referrals = Referrals()

    async def delete_user(self, user, uid):

        logger.info("Deleting user %s", uid)
        print(user)
        print(uid)

        # This takes care of everything in the store
        # FIXME: But not blobs???  Actually I think it does.
        await user.delete()

        try:
            firebase_admin.auth.delete_user(uid)
        except Exception as f:
            logger.info("Exception (delete_user): %s", f)

    async def register_user(
            self, email, phone_number, display_name, password, app_id,
            ref=None,
    ):
        
        if self.domains:
            check_domain(email, self.domains)

        uid = str(uuid.uuid4())

        if ref != None:
            pkg = self.referrals.get_package(ref)
            if pkg == None:
                raise RuntimeError("Referral code '%s' is not valid" % ref)
        else:
            pkg = self.referrals.default_package()

        # This is a new user.
        profile = {
            "version": "v1",
            "creation": datetime.datetime.utcnow().isoformat(),
            "billing_name": "",
            "billing_address": [],
            "billing_city": "",
            "billing_county": "",
            "billing_country": "",
            "billing_postcode": "",
            "billing_vat": "",
            "billing_email": email,
            "billing_tel": "",
        }

        scope = [
            "vat", "filing-config", "books", "company",
            "ch-lookup", "render", "status", "corptax",
            "accounts", "commerce", "user"
        ]

        state = State(self.store)
        user = state.user(uid)

        # Transaction ID for the free transaction credit
        txid = str(uuid.uuid4())

        credtx = {
            "time": datetime.datetime.now().isoformat(),
            "type": "credit",
            "description": "Credit receipt for ref " + pkg.id,
            "id": txid,
            "email": email,
            "uid": uid,
            "valid": True,
            "order": {
                "items": [
                    {
                        "kind": "vat",
                        "description": "VAT return",
                        "quantity": pkg.join_up_credits.vat,
                    },
                    {
                        "kind": "corptax",
                        "description": "Corp. tax filing",
                        "quantity": pkg.join_up_credits.corptax,
                    },
                    {
                        "kind": "accounts",
                        "description": "Accounts filing",
                        "quantity": pkg.join_up_credits.accounts,
                    }
                ]
            }
        }

        try:

            logger.info("Creating user profile...")
            await user.put(profile)

            logger.info("Setting balance...")
            await user.credits().put({
                "vat": pkg.join_up_credits.vat,
                "corptax": pkg.join_up_credits.corptax,
                "accounts": pkg.join_up_credits.accounts,
            })

            if pkg.join_up_credits.vat != 0 or pkg.join_up_credits.corptax != 0 or pkg.join_up_credits.accounts != 0:
                logger.info("Credit transaction...")
                await user.transaction(txid).put(credtx)

            logger.info("Setting package...")
            await user.package(pkg.id).put(pkg.to_dict())
            await user.currentpackage().put(pkg.to_dict())

            logger.info("Create user auth...")
            firebase_admin.auth.create_user(
                uid=uid, email=email,
                phone_number=phone_number,
                password=password,
                display_name=display_name,
                disabled=False
            )

            logger.info("Custom claim...")
            firebase_admin.auth.set_custom_user_claims(
                uid, { "scope": scope, "application-id": app_id }
            )

            logger.info("User creation complete.")

            return uid

        except Exception as e:

            # Need to attempt to back-track on all of the above setup
            logger.info("User create failed for %s", uid)

            # Tidy up, back-track
            try:
                await user.currentpackage().delete()
            except Exception as f:
                logger.info("Exception: %s", f)

            # Tidy up, back-track
            try:
                await user.package(pkg.id).delete()
            except Exception as f:
                logger.info("Exception: %s", f)

            # Delete transaction
            try:
                await user.transaction(txid).delete()
            except Exception as f:
                logger.info("Exception: %s", f)

            # Tidy up, back-track
            try:
                await user.credits().delete()
            except Exception as f:
                logger.info("Exception: %s", f)

            # Tidy up, back-track
            try:
                await user.delete()
            except Exception as f:
                logger.info("Exception: %s", f)

            try:
                firebase_admin.auth.delete_user(uid)
            except Exception as f:
                logger.info("Exception (register_user): %s", f)

            raise e

    async def verify_token(self, token):
        
        try:
            # Annoying - not async?
            # FIXME: Not async
            auth = firebase_admin.auth.verify_id_token(token)
        except:
            logger.info("Token not valid")
            raise AuthHeaderFailure()

        if (auth["exp"] <= time.time()):
            logger.info("Token expired.")
            raise AuthHeaderFailure()

        if not auth["email_verified"]:
            raise EmailNotVerified()
        
        if self.domains:
            try:
                check_domain(auth["email"], self.domains)
            except:
                raise BadDomain()

        # This shouldn't happen. I believe it's possible for an attacker
        # to use the Firebase API to create a user even though it's not in our
        # code, but they can't setup custom claims for the user.
        if "scope" not in auth:
            raise AuthHeaderFailure()

        scope = auth["scope"]

        logger.debug("OK %s %s", auth["sub"], scope)

        a = RequestAuth(auth["sub"], scope, self)
        a.email = auth["email"]

        return a

    async def get_profile(self, user):
        return await user.get()

    async def put_profile(self, user, profile):
        return await user.put(profile)

