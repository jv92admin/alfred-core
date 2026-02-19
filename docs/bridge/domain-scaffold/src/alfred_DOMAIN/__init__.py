"""Alfred DOMAIN — TODO: one-line description.

Importing this package registers the domain with Alfred's core engine.
"""

from alfred.domain import register_domain


def _register():
    from alfred_DOMAIN.domain import DOMAIN_CONFIG  # TODO: rename
    register_domain(DOMAIN_CONFIG)


_register()
