from loguru import logger

from clepsy import utils
from clepsy.auth.auth import hash_password as _hash
from clepsy.db import db_setup
from clepsy.db.db import get_db_connection
from clepsy.db.queries import create_user_auth, select_user_auth, select_user_settings


async def init():
    async with get_db_connection(include_uuid_func=False) as conn:
        try:
            await select_user_settings(conn)
            # Ensure user_auth is initialized on first boot
            auth_row = await select_user_auth(conn)
            if auth_row is None:
                bootstrap_pw = utils.get_bootstrap_password()
                await create_user_auth(conn, _hash(bootstrap_pw))

        except ValueError:
            logger.warning("User settings not found or database issue")

    await db_setup()

    # In RQ mode, no in-process event bus or workers are registered here.
