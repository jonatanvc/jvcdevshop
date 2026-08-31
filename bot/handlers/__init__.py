from .start import register_start_handlers
from .catalog import register_catalog_handlers
from .checkout import register_checkout_handlers
from .wallet import register_wallet_handlers
from .orders import register_orders_handlers
from .referrals import register_referrals_handlers
from .admin import register_admin_handlers

def register_all_handlers(app):
    register_start_handlers(app)
    register_catalog_handlers(app)
    register_checkout_handlers(app)
    register_wallet_handlers(app)
    register_orders_handlers(app)
    register_referrals_handlers(app)
    register_admin_handlers(app)
